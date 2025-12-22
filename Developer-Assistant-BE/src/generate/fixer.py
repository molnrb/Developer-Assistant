import asyncio
import json
from typing import Any, Dict, List, Optional

from src.run_utils.events import hub
from src.run_utils.fs_tools import apply_patches_in_memory
from src.run_utils.llm import chat_json
from src.run_utils.state import get_run

FIX_SYS = (
    "You are a TypeScript fixer agent for a React 18 + TypeScript app. "
    "Your job is to update exactly one existing file to fix TypeScript errors, "
    "without breaking the planned exports/imports contract. Output strict JSON."
)


def _plan_index(files: List) -> Dict[str, Dict[str, Any]]:
    """
    Build an index of plan files keyed by file name.
    """
    return {f["name"]: f for f in files if isinstance(f, dict)}


def _build_fix_prompt(
    description: str,
    plan_files_min: List[Dict[str, Any]],
    target_meta: Optional[Dict[str, Any]],
    path: str,
    content: str,
    errors: List[str],
) -> str:
    """
    Build a prompt for fixing a single file given its current content and TypeScript errors.
    """
    target_block = (
        {
            "name": path,
            "type": target_meta.get("type") if target_meta else None,
            "description": target_meta.get("description") if target_meta else None,
            "responsibilities": (
                target_meta.get("responsibilities", []) if target_meta else []
            ),
            "internalDependencies": (
                target_meta.get("internalDependencies", []) if target_meta else []
            ),
            "externalDependencies": (
                target_meta.get("externalDependencies", []) if target_meta else []
            ),
            "exports": target_meta.get("exports", []) if target_meta else [],
            "usedBy": target_meta.get("usedBy", []) if target_meta else [],
        }
        if target_meta is not None
        else {
            "name": path,
            "type": None,
            "description": None,
            "responsibilities": [],
            "internalDependencies": [],
            "externalDependencies": [],
            "exports": [],
            "usedBy": [],
        }
    )

    return f"""
High-level project description:
{description}

Goal
- Update the SINGLE target file to fix the TypeScript errors listed below.
- Keep all intended exports/imports and the file's high-level responsibilities intact.
- Use React 18 + TypeScript conventions.
- The result must be COMPLETE, runnable, and aligned with the plan.

Rules
- Output JSON only: {{ "content": "...", "summary": "..." }}
- Modify only this file.
- Do not introduce new files.
- Preserve planned exports/imports.
- Import only from internalDependencies or externalDependencies.
- Do not change import paths incorrectly.
- Avoid any; use proper TypeScript typings.
- All TypeScript errors must be fixed.

TypeScript errors:
{json.dumps(errors, ensure_ascii=False)}

Target metadata:
{json.dumps(target_block, ensure_ascii=False)}

Plan:
{json.dumps(plan_files_min, ensure_ascii=False)}

Current file content:
CONTENT_START
{content}
CONTENT_END

Your summary must describe what you fixed and why, without repeating metadata.
""".strip()


async def _fix_single_file(
    run_id: str,
    description: str,
    plan_index_by_name: Dict[str, Dict[str, Any]],
    plan_files_min: List[Dict[str, Any]],
    path: str,
    content: str,
    errors: List[str],
    model: str,
) -> Optional[Dict[str, Any]]:
    """
    Run the fixer LLM for a single file and return a patches object with summary.
    """
    target_meta = plan_index_by_name.get(path)

    try:
        user_prompt = _build_fix_prompt(
            description=description,
            plan_files_min=plan_files_min,
            target_meta=target_meta,
            path=path,
            content=content,
            errors=errors,
        )
        resp = await chat_json(
            run_id,
            "fixer",
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": FIX_SYS},
                {"role": "user", "content": user_prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        new_content = data.get("content")
        summary = data.get("summary", "")

        if not isinstance(new_content, str) or not new_content.strip():
            raise ValueError("Fixer returned empty content.")

        patches = [{"path": path, "content": new_content}]

        await hub.emit(
            run_id,
            {"t": "log", "stream": "stdout", "chunk": f"[fix] {path}\n{summary}"},
        )

        return {"summary": summary, "patches": patches}

    except Exception as e:
        await hub.emit(
            run_id,
            {"t": "log", "stream": "stderr", "chunk": f"[fix-fail] {path}: {e}"},
        )
        return None


async def fix_typescript_errors(
    run_id: str,
    description: str,
    model: str,
    concurrency: int = 4,
) -> bool:
    """
    Run a repair pass over files with TypeScript errors.
    Uses tsc_errors_by_file in run state and preserves the plan's import/export contract.
    """
    """if os.getenv("DEVMODE") == "true":
        await asyncio.sleep(1)
        r = get_run(run_id)
        log = "[dev] Skipping fixer"
        r["messages"].append(
            ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
        )
        await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
        await hub.emit(run_id, {"t": "status", "step": "fix", "state": "done"})
        return True"""

    r = get_run(run_id)
    errors_by_file = r.get("tsc_errors_by_file") or {}
    await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": "[fix] Starting fixer"})
    await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": f"[fix] Found {errors_by_file} files with TS errors"})
    current_files = r.get("modified_files", {}) or r.get("files", {}) or {}
    manifest = r.get("manifest", [])

    if not errors_by_file:
        await hub.emit(
            run_id, {"t": "log", "stream": "stdout", "chunk": "[fix] No TS errors"}
        )
        await hub.emit(run_id, {"t": "status", "step": "fix", "state": "done"})
        return True

    await hub.emit(run_id, {"t": "status", "step": "fix", "state": "running"})

    plan_index = _plan_index(manifest)
    plan_files_min = [
        {
            "name": f.get("name"),
            "type": f.get("type"),
            "description": f.get("description"),
            "responsibilities": f.get("responsibilities", []),
            "internalDependencies": f.get("internalDependencies", []),
            "externalDependencies": f.get("externalDependencies", []),
            "exports": f.get("exports", []),
            "usedBy": f.get("usedBy", []),
        }
        for f in manifest
        if isinstance(f, dict)
    ]

    targets = [p for p in errors_by_file if p in current_files]

    if not targets:
        await hub.emit(
            run_id, {"t": "log", "stream": "stderr", "chunk": "[fix] No matching files"}
        )
        await hub.emit(run_id, {"t": "status", "step": "fix", "state": "failed"})
        return False

    sem = asyncio.Semaphore(concurrency)
    file_summaries = {}
    patches = []

    async def _task(path: str):
        async with sem:
            return await _fix_single_file(
                run_id,
                description,
                plan_index,
                plan_files_min,
                path,
                current_files[path],
                errors_by_file[path],
                model,
            )

    results = await asyncio.gather(
        *[_task(p) for p in targets], return_exceptions=False
    )

    for res in results:
        if not res or not isinstance(res, dict):
            continue
        ps = res.get("patches")
        if isinstance(ps, list):
            patches.extend(ps)
            first = ps[0] if ps else None
            path = first.get("path") if isinstance(first, dict) else None
        else:
            path = None
        summary = res.get("summary")
        if path and summary:
            file_summaries[path] = summary

    if not patches:
        await hub.emit(
            run_id, {"t": "log", "stream": "stderr", "chunk": "[fix] No patches"}
        )
        await hub.emit(run_id, {"t": "status", "step": "fix", "state": "failed"})
        return False

    apply_patches_in_memory(current_files, patches)
    r["files"] = current_files
    r["modified_files"] = current_files

    """for meta in manifest:
        if not isinstance(meta, dict):
            continue
        name = meta.get("name")
        if name in file_summaries:
            prev = meta.get("summary") or ""
            fix = file_summaries[name]
            meta["summary"] = (prev + " | Fix: " + fix) if prev else ("Fix: " + fix)

    r["manifest"] = manifest"""
    await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": "Fixer completed"})
    await hub.emit(run_id, {"t": "status", "step": "fix", "state": "done"})

    return True
