from __future__ import annotations

from typing import Any, Dict

from src.run_utils.db import load_project_summary
from src.run_utils.events import hub


async def load_manifest_for_project(project_id: str, user: str) -> Dict[str, Any]:
    return load_project_summary(project_id, user)


async def update_manifest_by_interpret(
    run_id: str,
) -> None:
    """
    Incrementally update manifest after MODIFY/FIX.

    For a first version, we can simply rebuild the manifest for all current files.
    Later you can optimize by only recomputing changed files.
    """

    from src.run_utils.state import get_run

    run = get_run(run_id)
    manifest = run.get("manifest", {})
    modify_plan = run.get("modify", {})

    await hub.emit(
        run_id,
        {
            "t": "log",
            "stream": "stdout",
            "chunk": "Recomputing manifest from updated files.",
        },
    )

    for modified_file in modify_plan.get("changes", []):
        if modified_file.get("kind") == "delete_file":
            manifest = [
                file
                for file in manifest
                if file.get("name") != modified_file.get("name")
            ]
            continue
        elif modified_file.get("kind") == "new_file":
            new_file_entry = {
                "name": modified_file.get("name", ""),
                "type": modified_file.get("type", ""),
                "description": modified_file.get("description", ""),
                "responsibilities": modified_file.get("responsibilities", ""),
                "recentChanges": modified_file.get("recentChanges", ""),
                "exports": modified_file.get("exports", []),
                "internalDependencies": modified_file.get("internalDependencies", []),
                "externalDependencies": modified_file.get("externalDependencies", []),
                "usedBy": modified_file.get("usedBy", []),
            }
            manifest.append(new_file_entry)
        else:
            for file in manifest:
                if file.get("name") == modified_file.get("name"):
                    file["type"] = modified_file.get("type", "")
                    file["exports"] = modified_file.get("exports", "")
                    file["props"] = modified_file.get("props", "")
                    file["internalDependencies"] = modified_file.get(
                        "internalDependencies", ""
                    )
                    file["externalDependencies"] = modified_file.get(
                        "externalDependencies", ""
                    )
                    file["usedBy"] = modified_file.get("usedBy", "")
                    file["description"] = modified_file.get("description", "")
                    file["responsibilities"] = modified_file.get("responsibilities", "")
                    break

    run["manifest"] = manifest
