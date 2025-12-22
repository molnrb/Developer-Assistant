from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from src.modify.interpret import ChangesResponse
from src.run_utils.events import hub
from src.run_utils.fs_tools import apply_patches_in_memory
from src.run_utils.llm import chat_json
from src.run_utils.state import get_run
from src.api.database.database_dto import ChatMessage

IMPL_SYS = (
    "You are a code modifier agent for a React 18 + TypeScript project.\n"
    "You receive:\n"
    "- A target file path.\n"
    "- The current file content (possibly empty for new files).\n"
    "- A list of small edit operations (ops) describing what must change.\n"
    "- Lightweight manifest metadata about the file and its dependencies.\n\n"
    "Your job:\n"
    "- For existing files: apply the requested changes as minimally as possible.\n"
    "- For new files: create idiomatic, clean, type-safe React + TypeScript code.\n"
    "- Preserve TypeScript type safety.\n\n"
    "CRITICAL TYPE CONTRACT RULES:\n"
    "- Treat existing TypeScript interfaces, type aliases, enums, and exported component props as PUBLIC CONTRACTS.\n"
    "- Do NOT change these contracts (rename/remove fields, change field types, change function signatures)\n"
    "  UNLESS an op explicitly requires it.\n"
    "- If ops only describe behavior or rendering changes, do NOT modify interfaces or exported types.\n"
    "- If a new field is explicitly requested, add it in a backwards-compatible way and keep existing fields intact.\n\n"
    "Output format (STRICT):\n"
    "{\n"
    '  "patches": [\n'
    '    {"path": "<exact target path>", "mode": "update" | "create", "content": "<full new file content>"}\n'
    "  ],\n"
    '  "summary": "<one-line summary of what changed>"\n'
    "}\n"
    "- Return ONLY this JSON object. No markdown, no backticks, no extra text.\n"
)


def _ensure_manifest_list(manifest: Any) -> List[Dict[str, Any]]:
    """Normalize manifest into a list of file entries."""
    if isinstance(manifest, list):
        return [m for m in manifest if isinstance(m, dict)]
    return []


def _manifest_index_by_name(
    manifest_list: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Index manifest entries by file name."""
    return {
        item.get("name"): item
        for item in manifest_list
        if isinstance(item.get("name"), str)
    }


def _dep_blobs_from_manifest(
    target_name: str,
    manifest_index: Dict[str, Dict[str, Any]],
    current_files: Dict[str, str],
) -> List[Tuple[str, str]]:
    """Collect (path, content) for internalDependencies of a target file that exist in current_files."""
    item = manifest_index.get(target_name)
    if not item:
        return []

    deps = item.get("internalDependencies") or []
    if not isinstance(deps, list):
        return []

    blobs: List[Tuple[str, str]] = []
    for dep in deps:
        if isinstance(dep, str) and dep in current_files:
            blobs.append((dep, current_files[dep]))
    return blobs


def per_file_prompt(
    target_name: str,
    ops: List[Dict[str, Any]],
    original: str,
    manifest_file_meta: Dict[str, Any],
    dep_file_blobs: List[Tuple[str, str]],
    is_new_file: bool,
) -> str:
    """Build LLM prompt for modifying or creating a single file."""
    ops_json = json.dumps(ops or [], ensure_ascii=False, indent=2)
    meta_json = json.dumps(manifest_file_meta or {}, ensure_ascii=False, indent=2)

    def _truncate(s: str, limit: int = 40000) -> str:
        if len(s) <= limit:
            return s
        head = s[: int(limit * 0.7)]
        tail = s[-int(limit * 0.2) :]
        return head + "\n/* ... truncated ... */\n" + tail

    dep_payload = [{"path": p, "content": _truncate(c)} for (p, c) in dep_file_blobs]

    first_intent = ""
    if ops and isinstance(ops[0], dict):
        first_intent = ops[0].get("description") or ""

    mode_description = (
        "You will CREATE exactly ONE NEW file in a React 18 + TypeScript project."
        if is_new_file
        else "You will UPDATE exactly ONE existing file in a React 18 + TypeScript project."
    )

    return f"""
{mode_description}

Target file path:
{target_name}

High-level intent (from first op, if any):
{first_intent or "(none provided)"}

Operations (ops JSON):
{ops_json}

Guidelines:
- Treat the ops as the single source of truth for what must change.
- For existing files, keep unaffected parts of the file as-is.
- Do NOT modify public TypeScript contracts (interfaces, types, props, enums)
  unless an op explicitly requires it.

File metadata from manifest (JSON):
{meta_json}

Dependency files (read-only context):
{json.dumps(dep_payload, ensure_ascii=False)}

Current file content:
<<FILE_START>>
{original}
<<FILE_END>>

Now produce the updated or newly created file.

IMPORTANT OUTPUT RULES:
- Return ONLY a JSON object with this shape:
  {{
    "patches":[{{"path":"{target_name}","mode":"update"|"create","content":"<full new file content>"}}],
    "summary":"<one-line summary>"
  }}
- "path" MUST be exactly "{target_name}".
- "content" MUST be the FULL new file contents (not a diff).
- No markdown, no backticks, no extra prose.
""".strip()


async def _modify_single_file(
    run_id: str,
    target_name: str,
    ops: List[Dict[str, Any]],
    manifest_index: Dict[str, Dict[str, Any]],
    current_files: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Call LLM to modify or create a single file and return its patch object."""
    is_new_file = bool(ops) and all(
        isinstance(op, dict) and op.get("modify_kind") == "new_file" for op in ops
    )

    if target_name not in current_files and not is_new_file:
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"[skip] {target_name}: no current file content in run.files",
            },
        )
        return None

    original = "" if is_new_file else current_files.get(target_name, "")
    manifest_file_meta = manifest_index.get(target_name, {})
    dep_blobs = _dep_blobs_from_manifest(target_name, manifest_index, current_files)

    try:
        user_prompt = per_file_prompt(
            target_name, ops, original, manifest_file_meta, dep_blobs, is_new_file
        )
        resp = await chat_json(
            run_id,
            "implementer.modify",
            model="gpt-5-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": IMPL_SYS},
                {"role": "user", "content": user_prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content)

        patches = data.get("patches")
        if not isinstance(patches, list) or len(patches) != 1:
            raise ValueError("Expected exactly one patch in 'patches'.")
        p = patches[0]
        if p.get("path") != target_name:
            raise ValueError(
                f"Patch path must equal target file '{target_name}', got '{p.get('path')}'."
            )
        if p.get("mode") not in ("update", "create"):
            raise ValueError("Patch mode must be 'update' or 'create'.")
        if not isinstance(p.get("content"), str) or not p.get("content"):
            raise ValueError("Patch content must be a non-empty string.")

        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stdout",
                "chunk": f"Modified {target_name}\n{data.get('summary', '')}",
            },
        )
        return data

    except Exception as e:
        await hub.emit(
            run_id,
            {"t": "log", "stream": "stderr", "chunk": f"[fail] {target_name}: {e}"},
        )
        return None


async def generate_modify_scaffold(
    run_id: str,
    plan: ChangesResponse,
    *,
    concurrency: int = 8,
) -> bool:
    """
    Apply a structured modify plan (ChangesResponse) to the in-memory file set in iterations.
    """
    await hub.emit(run_id, {"t": "status", "step": "implement", "state": "running"})

    try:
        r = get_run(run_id)
        iterations: List[List[str]] = r.get("file_order_iterations") or []
        if not iterations:
            raise ValueError("Missing 'file_order_iterations' in run state")

        manifest_list = _ensure_manifest_list(r.get("manifest"))
        manifest_index = _manifest_index_by_name(manifest_list)

        original_files: Dict[str, str] = r.get("files", {}) or {}
        modified_files: Dict[str, str] = dict(original_files)

        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stdout",
                "chunk": f"Implementer (modify): {len(iterations)} iterations",
            },
        )

        raw_changes: List[Dict[str, Any]] = plan.get("changes", []) or []
        plan_by_path: Dict[str, List[Dict[str, Any]]] = {}
        change_summary_lines: List[Dict[str, Any]] = []
        for change in raw_changes:
            if not isinstance(change, dict):
                continue
            path = change.get("name")
            if not isinstance(path, str):
                continue
            plan_by_path.setdefault(path, []).append(change)

        all_iteration_paths = {name for layer in iterations for name in layer}
        extra_paths = set(plan_by_path.keys()) - all_iteration_paths
        if extra_paths:
            iterations.append(sorted(extra_paths))

        for idx, layer in enumerate(iterations):
            await hub.emit(
                run_id,
                {
                    "t": "status",
                    "step": f"implement.iter.{idx + 1}/{len(iterations)}",
                    "state": "running",
                },
            )
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": f"Iteration {idx + 1}: {len(layer)} files in layer",
                },
            )

            sem = asyncio.Semaphore(concurrency)
            deleted_paths_iter: List[str] = []

            async def _task(target_name: str) -> Optional[Dict[str, Any]]:
                file_changes = plan_by_path.get(target_name)
                if not file_changes:
                    await hub.emit(
                        run_id,
                        {
                            "t": "log",
                            "stream": "stdout",
                            "chunk": f"[skip] {target_name}: not in modify plan",
                        },
                    )
                    return None

                kinds = {
                    c.get("modify_kind")
                    for c in file_changes
                    if isinstance(c, dict) and c.get("modify_kind") is not None
                }

                if kinds == {"delete_file"}:
                    if target_name in modified_files:
                        del modified_files[target_name]
                        deleted_paths_iter.append(target_name)
                        await hub.emit(
                            run_id,
                            {
                                "t": "log",
                                "stream": "stdout",
                                "chunk": f"Deleted file {target_name}",
                            },
                        )
                    else:
                        await hub.emit(
                            run_id,
                            {
                                "t": "log",
                                "stream": "stderr",
                                "chunk": f"[skip] {target_name}: delete_file requested but file not present",
                            },
                        )
                    return None

                async with sem:
                    return await _modify_single_file(
                        run_id=run_id,
                        target_name=target_name,
                        ops=file_changes,
                        manifest_index=manifest_index,
                        current_files=modified_files,
                    )

            tasks = [_task(name) for name in layer]
            results = await asyncio.gather(*tasks, return_exceptions=False)

            patches: List[Dict[str, Any]] = []
            for res in results:
                if not res:
                    continue
                if isinstance(res, Dict) and isinstance(res.get("patches"), list):
                    patches.extend(res["patches"])
                if isinstance(res, Dict) and isinstance(res.get("summary"), str):
                    change_summary_lines.append(
                        {str(res["patches"][0]["path"]): res["summary"]}
                    )
                    log = f"{str(res['patches'][0]['path'])} change summary: {res.get('summary')}"
                    r["messages"].append(
                        ChatMessage(
                            id=r.get("messages", [])[-1].id + 1
                            if r.get("messages", [])
                            else 0,
                            content=log,
                            fromUser=False,
                        )
                    )
                    await hub.emit(
                        run_id,
                        {
                            "t": "log",
                            "stream": "stdout",
                            "chunk": log,
                        },
                    )

            changed_paths: List[str] = []
            if patches:
                changed_paths = apply_patches_in_memory(modified_files, patches)

            if deleted_paths_iter:
                changed_paths.extend(deleted_paths_iter)

            if not changed_paths:
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stderr",
                        "chunk": f"Iteration {idx + 1}: no patches or deletions produced",
                    },
                )
                continue

            await hub.emit(run_id, {"t": "patch.applied", "paths": changed_paths})
            await hub.emit(
                run_id,
                {
                    "t": "files.tree",
                    "paths": sorted(modified_files.keys())[:200],
                },
            )
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": f"Iteration {idx + 1}: applied {len(changed_paths)} file changes",
                },
            )

        r["modified_files"] = modified_files
        r["change_summaries"] = change_summary_lines

        await hub.emit(run_id, {"t": "status", "step": "implement", "state": "done"})
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stdout",
                "chunk": "Implementer (modify) completed all iterations.",
            },
        )

        return True

    except Exception as e:
        await hub.emit(
            run_id,
            {"t": "log", "stream": "stderr", "chunk": f"Implementer failed: {e}"},
        )
        await hub.emit(run_id, {"t": "status", "step": "implement", "state": "failed"})
        return False
