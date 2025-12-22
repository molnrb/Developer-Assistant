from __future__ import annotations

import json
from typing import Any, Dict, List, TypedDict, Literal

from src.run_utils.events import hub
from src.run_utils.llm import chat_json


class ExportSpec(TypedDict, total=False):
    name: str
    kind: str
    propsInterface: str
    description: str
    signature: str


class Change(TypedDict, total=False):
    """
    A single file's modified specification + the modification type/description.
    """

    name: str
    type: str
    description: str
    responsibilities: List[str]
    props: List[str]
    externalDependencies: List[str]
    internalDependencies: List[str]
    usedBy: List[str]
    exports: List[ExportSpec]

    modify_kind: str
    modify_desc: str


class ChangesResponse(TypedDict):
    changes: List[Change]


class PlannedChange(TypedDict):
    """
    Lightweight planner-level description: which file, what kind of change, and why.
    """

    name: str
    type: str
    modify_kind: Literal["edit", "new_file", "delete_file"]
    reason: str


class PlanResponse(TypedDict):
    planned_changes: List[PlannedChange]


class ChangesValidationError(Exception):
    def __init__(self, message: str, response: Dict[str, Any], failures: List[str]):
        super().__init__(message)
        self.response = response
        self.failures = failures


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _get_manifest_files(manifest: Any) -> List[Dict[str, Any]]:
    """
    Helper to get the list of file descriptors from the manifest.

    Supports:
    - [{"name": ...}, ...]  (manifest is already a list of file dicts)
    - {"files": [ ... ]}    (preferred object shape)
    """
    if isinstance(manifest, list):
        return manifest

    if isinstance(manifest, dict):
        files = manifest.get("files")
        if isinstance(files, list):
            return files

    return []



def build_planner_manifest(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build a lightweight manifest for the planner step:
    only fields needed to decide WHICH files are impacted.
    """
    result: List[Dict[str, Any]] = []
    for f in _get_manifest_files(manifest):
        result.append(
            {
                "name": f.get("name"),
                "type": f.get("type"),
                "description": _truncate(f.get("description", "") or "", 300),
                "responsibilities": f.get("responsibilities", []),
                "internalDependencies": f.get("internalDependencies", []),
                "externalDependencies": f.get("externalDependencies", []),
                "usedBy": f.get("usedBy", []),
            }
        )
    return result


def build_detailed_manifest_for_plan(
    manifest: Dict[str, Any],
    plan: PlanResponse,
) -> Dict[str, Any]:
    """
    Restrict the manifest to only those files that the planner marked as impacted.
    """
    files_by_name = {f.get("name"): f for f in _get_manifest_files(manifest)}
    selected_files: List[Dict[str, Any]] = []

    for ch in plan.get("planned_changes", []):
        name = ch.get("name")
        if name in files_by_name:
            selected_files.append(files_by_name[name])

    return {"files": selected_files}


def _build_system_prompt() -> str:
    return (
        "You are a senior full-stack engineer. Your task is to produce a precise, minimal set of\n"
        "FILE-LEVEL changes for a TypeScript/React project, based on a manifest that describes\n"
        "every file in the project.\n\n"
        "You will receive:\n"
        "1) A natural-language user request.\n"
        "2) A manifest describing all current project files (or a subset of them).\n"
        "3) A prior planning step that already decided WHICH files to touch and WHAT kind of\n"
        "   modification they need.\n\n"
        "YOUR OUTPUT MUST BE STRICT JSON:\n"
        '{ \"changes\": [ { ... }, { ... } ] }\n'
        "No prose. No markdown. No comments. JSON only.\n\n"
        "BEHAVIOR RULES:\n"
        "• Prefer returning one or more concrete file-level changes that would reasonably address\n"
        "  the user request.\n"
        "• If you are NOT fully sure what the exact implementation looks like, you may still return\n"
        "  CANDIDATE changes: pick the most relevant files and in `modify_desc` explain, in natural\n"
        "  language, what should be changed IF the implementation matches your assumptions.\n"
        "  Example: \"If GameBoard uses absolute positioning for tiles, switch to CSS grid with\n"
        "  gridTemplateColumns = repeat(size, 1fr) so tiles stay square.\"\n"
        "• Only if you truly cannot identify ANY reasonable candidate file or change for the request,\n"
        "  you may return an EMPTY `changes` array: { \"changes\": [] }.\n\n"
        "STRUCTURE RULES:\n"
        "• Each change must include modify_kind and modify_desc.\n"
        "• modify_kind must be one of: edit | new_file | delete_file.\n\n"
        "Each change object MUST have:\n"
        "  name, type, description, responsibilities, props, externalDependencies,\n"
        "  internalDependencies, usedBy, exports, modify_kind, modify_desc.\n\n"
        "For existing files, 'name' must match the manifest exactly. For new files, it must not exist.\n"
        "Be dependency-aware: if you change any export, you must also update dependents.\n"
        "Only JSON. Output nothing else."
    )


def _build_planner_system_prompt() -> str:
    return (
        "You are a senior full-stack engineer.\n"
        "Your ONLY job in this step is to decide WHICH FILES should be changed in a TypeScript/React\n"
        "project for a given user request, and WHAT KIND of change they need.\n\n"
        "You are NOT writing detailed implementation specs here.\n"
        "You only output a compact list of planned changes.\n\n"
        "STRICT JSON ONLY:\n"
        "{ \"planned_changes\": [ { ... }, { ... } ] }\n\n"
        "Each planned change must have:\n"
        "  - name (string, file path)\n"
        "  - type (string, e.g. component/page/hook/...)\n"
        "  - modify_kind (edit | new_file | delete_file)\n"
        "  - reason (short natural-language justification)\n\n"
        "Prefer returning a SMALL number of files (e.g. 1–5) that are most relevant.\n"
        "If you truly cannot identify any reasonable file-level impact, return:\n"
        "{ \"planned_changes\": [] }"
    )


def _build_planner_user_prompt(
    prompt: str,
    planner_manifest: List[Dict[str, Any]],
) -> str:
    return (
        "User request for modification:\n"
        f"{prompt}\n\n"
        "Project files (lightweight manifest):\n"
        f"{json.dumps(planner_manifest, ensure_ascii=False)}\n\n"
        "Decide which files should be EDITED, DELETED, or which NEW files should be created.\n"
        "Return ONLY the JSON object: { \"planned_changes\": [ ... ] }"
    )


def _build_detailer_user_prompt(
    prompt: str,
    plan: PlanResponse,
    detailed_manifest: Dict[str, Any],
) -> str:
    return (
        "User request for modification:\n"
        f"{prompt}\n\n"
        "Planned file-level impacts (from a previous planning step):\n"
        f"{json.dumps(plan, ensure_ascii=False)}\n\n"
        "Relevant project files (detailed manifest):\n"
        f"{json.dumps(detailed_manifest, ensure_ascii=False)}\n\n"
        "You MUST now produce a precise JSON object of file-level changes.\n"
        "Your output MUST follow this schema:\n"
        "{ \"changes\": [ { ... } ] }\n\n"
        "Each change MUST include: name, type, description, responsibilities,\n"
        "props, externalDependencies, internalDependencies, usedBy, exports,\n"
        "modify_kind, modify_desc.\n\n"
        "Use `modify_kind` from the plan when applicable.\n"
        "Return ONLY the JSON object: { \"changes\": [ ... ] }"
    )


async def call_llm_json(
    run_id: str,
    op_name: str,
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-5.1",
) -> Dict[str, Any]:
    try:
        resp = await chat_json(
            run_id,
            op_name,
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        print(f"Error during LLM call ({op_name}):", e)
        raise

    content = resp.choices[0].message.content
    if content is None:
        raise ValueError(f"No content returned from LLM for op {op_name}.")
    return json.loads(content)


def validate_changes(raw: Dict[str, Any]) -> ChangesResponse:
    failures: List[str] = []

    if not isinstance(raw, dict):
        failures.append("Top-level must be an object.")
        raise ChangesValidationError("Change plan validation failed", raw, failures)

    changes = raw.get("changes")
    if not isinstance(changes, list):
        failures.append("'changes' must be a list.")
        raise ChangesValidationError("Change plan validation failed", raw, failures)

    if len(changes) == 0:
        return raw

    required_keys = [
        "name",
        "type",
        "description",
        "responsibilities",
        "externalDependencies",
        "internalDependencies",
        "exports",
        "usedBy",
        "modify_kind",
        "modify_desc",
    ]

    allowed_file_types = {
        "component",
        "page",
        "hook",
        "context",
        "data",
        "style",
        "util",
        "router",
        "entry",
        "config",
    }

    allowed_modify_kinds = {"edit", "new_file", "delete_file"}

    list_fields = [
        "responsibilities",
        "props",
        "internalDependencies",
        "externalDependencies",
        "usedBy",
        "exports",
    ]

    for idx, ch in enumerate(changes):
        if not isinstance(ch, dict):
            failures.append(f"changes[{idx}] must be an object.")
            continue

        for k in required_keys:
            if k not in ch:
                failures.append(f"changes[{idx}] missing `{k}`.")

        name = ch.get("name")
        typ = ch.get("type")
        description = ch.get("description")
        modify_kind = ch.get("modify_kind")
        modify_desc = ch.get("modify_desc")

        if name is not None and (not isinstance(name, str) or not name.strip()):
            failures.append(f"changes[{idx}].name must be non-empty string.")

        if typ is not None:
            if not isinstance(typ, str) or typ not in allowed_file_types:
                failures.append(f"changes[{idx}].type invalid: {typ!r}")

        if description is not None and (
            not isinstance(description, str) or not description.strip()
        ):
            failures.append(f"changes[{idx}].description must be non-empty string.")

        if modify_kind is not None:
            if modify_kind not in allowed_modify_kinds:
                failures.append(f"changes[{idx}].modify_kind invalid: {modify_kind!r}")

        if modify_desc is not None and (
            not isinstance(modify_desc, str) or not modify_desc.strip()
        ):
            failures.append(f"changes[{idx}].modify_desc must be non-empty string.")

        for field in list_fields:
            if field in ch:
                value = ch[field]
                if not isinstance(value, list):
                    failures.append(f"changes[{idx}].{field} must be a list.")
                    continue

                for j, item in enumerate(value):
                    if field == "exports":
                        if not isinstance(item, dict):
                            failures.append(
                                f"changes[{idx}].exports[{j}] must be an object."
                            )
                            continue
                        for ek in [
                            "name",
                            "kind",
                            "propsInterface",
                            "description",
                            "signature",
                        ]:
                            if ek not in item:
                                failures.append(
                                    f"changes[{idx}].exports[{j}] missing `{ek}`."
                                )
                    else:
                        if not isinstance(item, str):
                            failures.append(
                                f"changes[{idx}].{field}[{j}] must be a string."
                            )

    if failures:
        raise ChangesValidationError(
            f"Change plan validation failed with {len(failures)} issues.",
            raw,
            failures,
        )

    return raw


async def reinterpret_changes(
    run_id: str,
    prompt: str,
    manifest: Dict[str, Any],
    bad_response: Dict[str, Any],
    failures: List[str],
    model: str = "gpt-5.1",
) -> ChangesResponse:

    system_prompt = _build_system_prompt()

    correction_prompt = (
        "Your previous JSON change plan was INVALID.\n"
        "You MUST fix ALL issues listed below:\n"
        f"{json.dumps(failures, ensure_ascii=False)}\n\n"
        "Here is your previous invalid JSON:\n"
        f"{json.dumps(bad_response, ensure_ascii=False)}\n\n"
        "You MUST output a NEW full JSON object.\n"
        "You may return an empty 'changes' array ONLY if you truly cannot identify any reasonable\n"
        "candidate change for the user request.\n\n"
        "User request:\n"
        f"{prompt}\n\n"
        "Manifest:\n"
        f"{json.dumps(manifest, ensure_ascii=False)}\n"
    )

    resp = await chat_json(
        run_id,
        "modify-reinterpreter",
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": correction_prompt},
        ],
    )

    content = resp.choices[0].message.content
    if content is None:
        raise ValueError("No content returned from LLM in reinterpret step.")
    data = json.loads(content)
    return validate_changes(data)


async def plan_impacted_files(
    run_id: str,
    prompt: str,
    manifest: Dict[str, Any],
    model: str = "gpt-5.1",
) -> PlanResponse:
    """
    First-phase planner: decide which files are impacted and how (edit/new/delete),
    using a lightweight manifest.
    """
    planner_manifest = build_planner_manifest(manifest)
    system_prompt = _build_planner_system_prompt()
    user_prompt = _build_planner_user_prompt(prompt, planner_manifest)

    raw = await call_llm_json(
        run_id,
        "modify-planner",
        system_prompt,
        user_prompt,
        model=model,
    )

    planned_changes = raw.get("planned_changes")
    if not isinstance(planned_changes, list):
        raise ValueError("Planner response missing 'planned_changes' list.")

    return raw


async def interpret_prompt_against_manifest(
    run_id: str,
    prompt: str,
    manifest: Dict[str, Any],
) -> ChangesResponse:
    """
    Two-phase interpretation:
    1) Planner: which files to touch and how.
    2) Detailer: full ChangesResponse only for those files (with full manifest).
    """
    plan = await plan_impacted_files(run_id, prompt, manifest)
    if not plan.get("planned_changes"):
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": (
                    "Planner could not identify any file-level impact "
                    "(returned empty 'planned_changes')."
                ),
            },
        )
        return {"changes": []}

    detailed_manifest = build_detailed_manifest_for_plan(manifest, plan)
    system_prompt = _build_system_prompt()
    user_prompt = _build_detailer_user_prompt(prompt, plan, detailed_manifest)

    raw = await call_llm_json(
        run_id,
        "modify-llm-interpret",
        system_prompt,
        user_prompt,
        model="gpt-5.1",
    )
    print(f"[MODIFY] detailer raw response: {raw}")

    changes = raw.get("changes")
    if isinstance(changes, list) and len(changes) == 0:
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": (
                    "Interpreter (detailer) could not find any safe file-level change to apply "
                    "for this request (returned an empty `changes` array)."
                ),
            },
        )
        return {"changes": []}

    try:
        return validate_changes(raw)
    except ChangesValidationError as e:
        
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": (
                    f"Initial detailer JSON failed with {len(e.failures)} issues, reinterpreting…"
                ),
            },
        )
        return await reinterpret_changes(
            run_id=run_id,
            prompt=prompt,
            manifest=detailed_manifest,
            bad_response=e.response,
            failures=e.failures,
        )
