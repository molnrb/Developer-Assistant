from __future__ import annotations

from typing import Dict, List

from src.api.database.database_dto import ChatMessage, ProjectFile
from src.run_utils.db import (
    add_messages_to_project,
    load_all_files,
    message_count_in_project,
    replace_project_files,
    replace_project_manifest,
)
from src.modify.interpret import interpret_prompt_against_manifest, reinterpret_changes
from src.run_utils.manifest import (
    load_manifest_for_project,
    update_manifest_by_interpret,
)
from src.modify.patch import generate_modify_scaffold
from src.generate.fixer import fix_typescript_errors
from src.generate.tester import run_tsc_check
from src.run_utils.events import hub
from src.run_utils.file_order_planner import compute_iterations_from_manifest
from src.run_utils.state import get_run
from src.utils.dto import Action

MAX_STEPS = 30
MAX_FIX = 5


async def run_modify_loop(run_id: str, prompt: str, user: str):
    """Main modify loop that applies changes to an existing project based on user prompt."""
    r = get_run(run_id)
    r.setdefault("state", {"current": "QUEUED"})
    r.setdefault("history", {"steps": [], "tries": {}})
    r.setdefault("counters", {"fix_loops": 0, "replan_loops": 0})
    r.setdefault("obs", {})
    r.setdefault("metrics", {})
    r.setdefault("files", {})
    r.setdefault("title", f"Modify: {prompt[:32]}")
    r.setdefault("budget", {"tokensLeft": 100000, "retries": 10})
    r["messages"] = [
        ChatMessage(
            id=message_count_in_project(run_id, user), content=prompt, fromUser=True
        )
    ]
    r["manifest"] = await load_manifest_for_project(run_id, user)
    r["files"] = load_all_files(run_id, user)
    iterations = compute_iterations_from_manifest(r["manifest"])
    r["file_order_iterations"] = iterations["iterations"]
    await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": r["manifest"]})

    try:
        for step in range(MAX_STEPS):
            a = _as_action(step_controller(r))
            await hub.emit(
                run_id, {"t": "controller.next", "action": a.action, "reason": a.reason}
            )
            print(f"[MODIFY] current action: {a.action} (step {step})")

            if a.action in ("STOP", None):
                await hub.emit(run_id, {"t": "done", "ok": False})
                break

            if a.action == "INTERPRET":
                r["state"]["current"] = "INTERPRET"
                await hub.emit(
                    run_id, {"t": "status", "step": "interpret", "state": "running"}
                )
                manifest = r.get("manifest") or {}
                print(f"[MODIFY] interpreting prompt against manifest (step {step})")
                interpretation = await interpret_prompt_against_manifest(
                    run_id, prompt, manifest
                )
                if len(interpretation.get("changes", "")) == 0:
                    log = "No changes proposed by interpretation; stopping modify loop.\n"
                    r["messages"].append(
                        ChatMessage(
                            id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                            content=log,
                            fromUser=False,
                        )
                    )
                    break
                
                r["modify"] = interpretation
                await hub.emit(
                    run_id, {"t": "status", "step": "interpret", "state": "done"}
                )
                changes = [f["name"] + ": " + f["modify_kind"] + "\nModify description" + f["modify_desc"] + "\n\n" for f in interpretation.get("changes", [])]
                log = f"Interpretation completed with changes:\n\n{changes}\n"
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
                
            elif a.action == "REINTERPRET":
                print(f"[MODIFY] re-interpreting prompt (step {step})")
                r["state"]["current"] = "REINTERPRET"
                await hub.emit(
                    run_id, {"t": "status", "step": "interpret", "state": "running"}
                )
                manifest = r.get("manifest") or {}
                interpretation = await reinterpret_changes(
                    run_id, prompt, manifest, r.get("modify", {}, r.get("tsc_errors_by_file", {}))
                )
                if len(interpretation.get("changes", "")) == 0:
                    log = "No changes proposed by reinterpretation; stopping modify loop.\n"
                    r["messages"].append(
                        ChatMessage(
                            id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                            content=log,
                            fromUser=False,
                        )
                    )
                    break
                r["modify"] = interpretation
                await hub.emit(
                    run_id, {"t": "status", "step": "interpret", "state": "done"}
                )
                changes = [f["name"] + ": " + f["modify_kind"] + "\nModify description" + f["modify_desc"] + "\n\n" for f in interpretation.get("changes", [])]
                log = f"Re-interpretation completed with changes:\n\n{changes}\n"
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})

            elif a.action == "MODIFY":
                r["state"]["current"] = "MODIFY"
                await hub.emit(
                    run_id, {"t": "status", "step": "modify", "state": "running"}
                )
                plan = r.get("modify")
                apply_ok = await generate_modify_scaffold(run_id, plan)
                if apply_ok:
                    await hub.emit(run_id, {"t": "manifest.updated"})
                r["history"]["steps"].append(
                    {"step": step, "action": "MODIFY", "ok": bool(apply_ok)}
                )
                log = "Modify scaffold generation completed.\n"
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
                await hub.emit(run_id, {"t": "status", "step": "modify", "state": "done"})

            elif a.action == "TEST":
                r["state"]["current"] = "TEST"
                await hub.emit(run_id, {"t": "status", "step": "test", "state": "running"})
                passed = await run_tsc_check(run_id)
                r["obs"]["check_pass"] = bool(passed)
                r["obs"]["check_fail"] = not bool(passed)
                r["metrics"].setdefault("test", {})["ok"] = bool(passed)
                log = f"Type check {'passed' if passed else 'failed'}. Problematic files: {r.get('tsc_errors_by_file')}\n"
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
                await hub.emit(run_id, {"t": "test.result", "ok": bool(passed)})
                if passed:
                    await hub.emit(
                        run_id,
                        {"t": "log", "stream": "stdout", "chunk": "Type check passed."},
                    )
                    await hub.emit(run_id, {"t": "status", "step": "test", "state": "done"})

            elif a.action == "FIX":
                r["state"]["current"] = "FIX"
                await hub.emit(
                    run_id, {"t": "status", "step": "fix", "state": "running"}
                )
                changed = await fix_typescript_errors(run_id, prompt, "gpt-5-mini")
                r["counters"]["fix_loops"] = int(r["counters"].get("fix_loops", 0)) + 1
                r["history"]["steps"].append(
                    {"step": step, "action": "FIX", "changed": bool(changed)}
                )
                log = f"Fixer done; changes made: {changed}."
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
                await hub.emit(run_id, {"t": "status", "step": "fix", "state": "done"})
                
            elif a.action == "REPLAN":
                r["state"]["current"] = "REPLAN"
                r["counters"]["replan_loops"] = (
                    int(r["counters"].get("replan_loops", 0)) + 1
                )
                await hub.emit(
                    run_id, {"t": "status", "step": "impact", "state": "running"}
                )
                manifest = r.get("manifest") or {}
                interpretation = (r.get("modify") or {}).get("interpret", {})
                interpretation = {**interpretation, "observations": r.get("obs", {})}
                await hub.emit(run_id, {"t": "status", "step": "impact", "state": "done"})

            elif a.action == "PACKAGE":
                log = "Packaging project and updating database.\n"
                r["messages"].append(
                    ChatMessage(
                        id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                        content=log,
                        fromUser=False,
                    )
                )
                await hub.emit(run_id, {"t": "log", "stream": "stdout", "chunk": log})
                await update_manifest_by_interpret(run_id)
                r["state"]["current"] = None
                update_db(
                    run_id,
                    [
                        ProjectFile(name=n, content=c)
                        for n, c in r.get("modified_files", {}).items()
                    ],
                    [
                        ChatMessage(id=m.id, content=m.content, fromUser=m.fromUser)
                        for i, m in enumerate(r.get("messages", []))
                    ],
                    r.get("manifest", []),
                    user,
                )
                
                await hub.emit(run_id, {"t": "files.ready", "data": r.get("files", {})})
                await hub.emit(
                    run_id, {"t": "artifact.ready", "url": f"/runs/{run_id}/artifact.zip"}
                )
                await hub.emit(
                    run_id, {"t": "report.ready", "url": f"/runs/{run_id}/report"}
                )
                ok_flag = bool((r.get("metrics", {}).get("test") or {}).get("ok"))
                await hub.emit(run_id, {"t": "status", "step": "done", "state": "done"})
                await hub.emit(run_id, {"t": "done", "ok": ok_flag})

                r.setdefault("history", {}).setdefault("steps", []).append(
                    {"action": "PACKAGE", "ok": ok_flag}
                )
                r["finished"] = True
                r["finishedAt"] = __import__("time").time()
                break

            else:
                print(f"[MODIFY] unknown action: {a.action} (step {step})")
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stderr",
                        "chunk": f"Unknown action: {a.action}",
                    },
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "done",
                        "ok": bool((r.get("metrics", {}).get("test") or {}).get("ok")),
                    },
                )
                break

            if r["budget"].get("tokensLeft", 0) <= 0 or r["budget"].get("retries", 0) <= 0:
                await hub.emit(
                    run_id, {"t": "artifact.ready", "url": f"/runs/{run_id}/artifact.zip"}
                )
                await hub.emit(
                    run_id, {"t": "report.ready", "url": f"/runs/{run_id}/report"}
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "done",
                        "ok": bool((r.get("metrics", {}).get("test") or {}).get("ok")),
                    },
                )
                break

            r["history"]["steps"].append(
                {"step": step, "action": a.action, "reason": a.reason}
            )
    except Exception as e:
        log = f"[MODIFY] Exception in modify loop: {e}\n"
        await hub.emit(run_id, {"t": "log", "stream": "stderr", "chunk": log})
        r["messages"].append(
            ChatMessage(
                id=r.get("messages", [])[-1].id + 1 if r.get("messages", []) else 0,
                content=log,
                fromUser=False,
            )
        )
        await hub.emit(
            run_id,
            {
                "t": "done",
                "ok": bool((r.get("metrics", {}).get("test") or {}).get("ok")),
            },
        )
        r["state"]["current"] = "STOP"


def step_controller(run):
    """Deterministic state machine that decides the next action."""
    s = run["state"].get("current")
    o = run.get("obs", {})
    c = run.get("counters", {})
    b = run.get("budget", {})

    if b.get("tokensLeft", 0) <= 0 or b.get("retries", 0) <= 0:
        print("[MODIFY] budget exhausted")
        return Action("PACKAGE", reason="Budget exhausted; packaging current state")

    if s in (None, "QUEUED"):
        return Action("INTERPRET", reason="Start modify: interpret prompt vs manifest")

    if s == "INTERPRET":
        return Action("MODIFY", reason="Interpretation ready; plan localized edits")
    
    if s == "REINTERPRET":
        return Action("MODIFY", reason="Re-interpret after failed test")

    if s == "MODIFY":
        return Action("TEST", reason="Patches applied; run static checks/build")

    if s == "TEST":
        if o.get("check_pass"):
            return Action("PACKAGE", reason="Checks passed; finalize")
        if o.get("check_fail"):
            if c.get("fix_loops", 0) < MAX_FIX:
                return Action(
                    "FIX",
                    reason="Checks failed; reflect & propose minimal fixes",
                )
            return Action("REINTERPRET", reason="Failed after retries; REINTERPRET")
        return Action("PACKAGE", reason="Waiting for check result")

    if s == "FIX":
        return Action("TEST", reason="Re-test after fixes")
    
    if s == "STOP":
        return Action("STOP", reason="Run already marked as stopped")

    if s == "PACKAGE":
        return Action("STOP", reason="Modify run complete")


def _as_action(a) -> Action:
    """Convert any value to Action object."""
    if isinstance(a, Action):
        return a
    return Action(action=str(a or "STOP"))


def update_db(
    project_id: str,
    new_files: List[ProjectFile],
    new_messages: List[ChatMessage],
    new_manifest: List[Dict],
    username: str,
) -> None:
    """Update database with modified project files, messages, and manifest."""
    replace_project_files(project_id, new_files, username)
    add_messages_to_project(project_id, new_messages, username)
    replace_project_manifest(project_id, new_manifest, username)
