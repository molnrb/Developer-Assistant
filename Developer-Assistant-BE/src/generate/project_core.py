from __future__ import annotations

import asyncio
import traceback
from typing import Any, Dict

from src.api.database.database_dto import ChatMessage, ProjectCreateRequest, ProjectFile
from src.api.database.database_service import DatabaseService
from src.generate.fixer import fix_typescript_errors
from src.generate.implementer import generate_scaffold
from src.generate.planner import generate_title, plan_project, replan
from src.generate.router import route_domain
from src.generate.sanity import sanity_check
from src.generate.tester import run_tsc_check
from src.run_utils.events import hub
from src.run_utils.file_order_planner import compute_iterations
from src.run_utils.state import get_run
from src.utils.dto import Action

MAX_STEPS = 30
MAX_FIX = 5
MAX_REPLAN = 1


async def run_agentic_loop(run_id: str, desc: str, override: str | None, planning_model: str, implementer_model: str, fixer_model: str, user: str):
    """Main agentic loop that creates a project from description through planning, implementation, and testing."""
    r = get_run(run_id)
    r["description"] = desc
    r.setdefault("budget", {"retries": 1, "tokensLeft": 100000})
    r.setdefault("history", {"steps": [], "tries": {}})
    r.setdefault("title", "Untitled Run")
    r.setdefault("metrics", {})
    r.setdefault("files", {})
    r.setdefault("messages", [ChatMessage(id=0, content=desc, fromUser=True)])
    r.setdefault("state", {"current": "QUEUED"})
    r.setdefault("counters", {"fix_loops": 0, "replan_loops": 0})
    r.setdefault("replan_tries", 2)
    r.setdefault(
        "flags",
        {"manual_override": bool(override and override != "auto"), "e2e": False},
    )
    r.setdefault("obs", {})

    if r["flags"]["manual_override"]:
        r["router"] = {
            "domain": override,
            "confidence": 1.0,
            "rationale": "manual override",
        }
        await hub.emit(run_id, {"t": "router.result", **r["router"]})

    try:
        for step in range(MAX_STEPS):
            a = _as_action(step_controller(r))
            print(f"current action: {a.action} (step {step})")

            if a.action in ("STOP", None):
                await hub.emit(
                    run_id,
                    {
                        "t": "done",
                        "ok": bool((r.get("metrics", {}).get("test") or {}).get("ok")),
                    },
                )
                break

            if a.action == "ROUTE":
                r["state"]["current"] = "ROUTE"
                await hub.emit(
                    run_id, {"t": "status", "step": "router", "state": "running"}
                )
                res = await route_domain(run_id, desc)
                r["router"] = res
                await hub.emit(
                    run_id, {"t": "status", "step": "router", "state": "done"}
                )
                log = f"Routed to domain: {res.get('domain')} (confidence {res.get('confidence')})"
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )

            elif a.action == "PLAN":
                r["state"]["current"] = "PLAN"
                await hub.emit(
                    run_id, {"t": "status", "step": "planner", "state": "running"}
                )
                domain = (r.get("router") or {}).get("domain")
                title = await generate_title(desc)
                r["title"] = title
                await hub.emit(run_id, {"t": "title.generated", "title": title})
                log = f"Generated title: {title}"
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )

                plan = await plan_project(run_id, desc, domain, model=planning_model)
                r["plan"] = plan
                r["manifest"] = plan.get("files", [])
                await hub.emit(
                    run_id, {"t": "status", "step": "planner", "state": "done"}
                )
                log =f"Plan summary: {plan.get('summary','(no summary)')}"
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )
                log = f"```text {json_to_tree_string(plan)} \n```"
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )

            elif a.action == "REPLAN":
                r["state"]["current"] = "PLAN"
                await hub.emit(
                    run_id, {"t": "status", "step": "planner", "state": "running"}
                )
                plan = await replan(
                    run_id,
                    r.get("plan"),
                    desc,
                    r["sanity"],
                    (r.get("router") or {}).get("domain"),
                )
                r["plan"] = plan
                await hub.emit(
                    run_id, {"t": "status", "step": "planner", "state": "done"}
                )
                log = f"Replan created with {len(plan.get('files', []))} files:\n\n{json_to_tree_string(plan)}"

                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )

            elif a.action == "SANITY":
                r["state"]["current"] = "SANITY"
                await hub.emit(
                    run_id, {"t": "status", "step": "sanity", "state": "running"}
                )
                s = sanity_check(
                    r.get("plan", {}), (r.get("router") or {}).get("domain")
                )
                r["obs"]["sanity_ok"] = bool(s.get("ok"))
                if s.get("ok"):
                    await hub.emit(
                        run_id, {"t": "status", "step": "sanity", "state": "done"}
                    )
                    log = "Sanity check passed."
                    r["messages"].append(
                        ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                    )
                    await hub.emit(
                        run_id,
                        {"t": "log", "stream": "stdout", "chunk": log},
                    )
                else:
                    fails = s.get("fails", [])
                    r["sanity"] = fails
                    await hub.emit(
                        run_id, {"t": "status", "step": "sanity", "state": "failed"}
                    )
                    log = f"Sanity check failed: {fails}"
                    r["messages"].append(
                        ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                    )
                    await hub.emit(
                        run_id,
                        {
                            "t": "log",
                            "stream": "stderr",
                            "chunk": log,
                        },
                    )

            elif a.action == "IMPLEMENT":
                r["state"]["current"] = "IMPLEMENT"
                await hub.emit(
                    run_id, {"t": "status", "step": "implement", "state": "running"}
                )
                r["file_order_iterations"] = compute_iterations(r["plan"])
                await generate_scaffold(
                    run_id,
                    r.get("plan", {}),
                    (r.get("router") or {}).get("domain"),
                    desc,
                    r.get("file_order_iterations").get("iterations", []),
                    implementer_model,
                )
                log = "Implementation done; files now present."
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )
                await hub.emit(
                    run_id, {"t": "status", "step": "implement", "state": "done"}
                )

            elif a.action == "TEST":
                r["state"]["current"] = "TEST"
                await hub.emit(
                    run_id, {"t": "status", "step": "test", "state": "running"}
                )
                passed = await run_tsc_check(run_id)
                r["obs"]["check_pass"] = bool(passed)
                r["obs"]["check_fail"] = not bool(passed)
                r["metrics"].setdefault("test", {})["ok"] = bool(passed)

                log = f"Type check {'passed' if passed else 'failed'}. Problematic files: {r.get('tsc_errors_by_file')}\n"
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                if passed:
                    await hub.emit(
                        run_id,
                        {"t": "log", "stream": "stdout", "chunk": log},
                    )
                    await hub.emit(
                        run_id, {"t": "status", "step": "test", "state": "done"}
                    )

            elif a.action == "FIX":
                r["state"]["current"] = "FIX"
                await hub.emit(
                    run_id, {"t": "status", "step": "fix", "state": "running"}
                )
                changed = await fix_typescript_errors(run_id, description=desc, model=fixer_model)
                r["counters"]["fix_loops"] = int(r["counters"].get("fix_loops", 0)) + 1
                r["history"]["steps"].append(
                    {"step": step, "action": "FIX", "changed": bool(changed)}
                )
                log = f"Fixer done; changes made: {changed}."
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )
                await hub.emit(
                    run_id, {"t": "status", "step": "fix", "state": "done"}
                )

            elif a.action == "PACKAGE":
                db_service = DatabaseService()
                files = [
                    ProjectFile(name=name, content=content)
                    for name, content in r.get("files", {}).items()
                ]
                db_service.add_project(
                    ProjectCreateRequest(
                        id=run_id,
                        title=r.get("title", ""),
                        summary=r.get("manifest", ""),
                        files=files,
                        messages=r.get("messages", []),
                    ),
                    user,
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "done",
                        "ok": bool((r.get("metrics", {}).get("test") or {}).get("ok")),
                    },
                )
                log = "Project packaged and saved to database."
                r["messages"].append(
                    ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stdout",
                        "chunk": log,
                    },
                )
                ok_flag = bool((r.get("metrics", {}).get("test") or {}).get("ok"))
                await hub.emit(run_id, {"t": "status", "step": "done", "state": "done"})
                await hub.emit(run_id, {"t": "done", "ok": ok_flag})
                r["state"]["current"] = None
                r.setdefault("history", {}).setdefault("steps", []).append(
                    {"action": "PACKAGE", "ok": ok_flag}
                )
                r["finished"] = True
                r["finishedAt"] = __import__("time").time()

                break

            else:
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

            if bool((r.get("metrics", {}).get("test") or {}).get("ok")):
                pass

            if (
                r["budget"].get("tokensLeft", 0) <= 0
                or r["budget"].get("retries", 0) <= 0
            ):
                await hub.emit(
                    run_id,
                    {"t": "artifact.ready", "url": f"/runs/{run_id}/artifact.zip"},
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

            if a.action == "REPLAN":
                r["counters"]["replan_loops"] = (
                    int(r["counters"].get("replan_loops", 0)) + 1
                )

            r["history"]["steps"].append(
                {"step": step, "action": a.action, "reason": a.reason}
            )

    except asyncio.CancelledError:
        r["state"]["current"] = "STOP"
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": "Run was cancelled.",
            },
        )
        await hub.emit(run_id, {"t": "done", "ok": False, "error": "cancelled"})
        raise

    except Exception as e:
        tb = traceback.format_exc()
        r["state"]["current"] = "ERROR"
        r.setdefault("obs", {})["exception"] = repr(e)
        r.setdefault("history", {}).setdefault("steps", []).append(
            {"action": "ERROR", "error": repr(e)}
        )

        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"Unhandled error in run_agentic_loop: {e}\n{tb}",
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "done",
                "ok": False,
                "error": str(e),
            },
        )


def step_controller(run):
    """Deterministic state machine that decides the next action."""
    s = run["state"].get("current")
    o = run.get("obs", {})
    f = run.get("flags", {})
    c = run.get("counters", {})
    b = run.get("budget", {})

    has_files = bool(run.get("files"))
    compile_ok = bool((run.get("metrics", {}).get("test") or {}).get("ok"))
    sanity_ok = o.get("sanity_ok", None)
    manual = f.get("manual_override", False)

    if b.get("tokensLeft", 0) <= 0 or b.get("retries", 0) <= 0:
        return Action("PACKAGE", reason="Budget exhausted; packaging current state")

    if s in (None, "QUEUED"):
        if manual and run.get("router"):
            return Action("PLAN", reason="Manual override: skip ROUTE")
        return Action("ROUTE", reason="Starting route detection")

    if s == "ROUTE":
        return Action("PLAN", reason="Route ready; create plan")

    if s in ("PLAN", "REPLAN"):
        return Action("SANITY", reason="Plan done; running sanity check")

    if s == "SANITY":
        if sanity_ok is True:
            return Action(
                "IMPLEMENT", reason="Sanity passed; proceed to implementation"
            )
        if sanity_ok is False:
            if manual:
                return Action(
                    "IMPLEMENT", reason="Sanity failed but manual override enabled"
                )
            if c.get("replan_loops", 0) < MAX_REPLAN:
                return Action("REPLAN", reason="Sanity failed; try re-planning")
            return Action("ASK_USER", reason="Sanity failed and replan budget used")
        return Action("ASK_USER", reason="No sanity result; waiting for user")

    if s == "IMPLEMENT":
        if not has_files:
            return Action("IMPLEMENT", reason="No files yet; implement")
        return Action("TEST", reason="Files ready; run type check")

    if s == "TEST":
        if compile_ok or o.get("check_pass"):
            return Action("PACKAGE", reason="Compile passed; package results")
        if o.get("check_fail"):
            if c.get("fix_loops", 0) < MAX_FIX:
                return Action("FIX", reason="Compile failed; run fixer")
            if c.get("replan_loops", 0) < MAX_REPLAN:
                return Action("PACKAGE", reason="Compile still failing; replan")
            return Action(
                "PACKAGE", reason="Compile failed after retries; packaging anyway"
            )
        return Action("ASK_USER", reason="Waiting for check result")

    if s == "FIX":
        return Action("TEST", reason="Re-test after fixes")

    if s == "INTEG_TEST":
        if o.get("e2e_pass"):
            return Action("PACKAGE", reason="E2E passed; finalize")
        if o.get("e2e_fail") and c.get("fix_loops", 0) < MAX_FIX:
            return Action("FIX", reason="E2E failed; attempt minimal fix")
        if o.get("e2e_fail") and c.get("replan_loops", 0) < MAX_REPLAN:
            return Action("REPLAN", reason="E2E failed again; replan")
        return Action("PACKAGE", reason="E2E failed; packaging state")

    if s == "PACKAGE":
        return Action("STOP", reason="Run complete")

    if s == "STOP":
        return Action("STOP", reason="Run already marked as stopped")


def _as_action(a) -> Action:
    """Convert any value to Action object."""
    if isinstance(a, Action):
        return a
    return Action(action=str(a or "STOP"))


def json_to_tree_string(data: Dict[str, Any]) -> str:
    """Convert a plan dict to a tree-like string representation."""

    root: Dict[str, Any] = {}

    for f in data.get("files", []):
        path = f["name"]
        parts = path.split("/")

        current = root
        for i, part in enumerate(parts):
            is_file = i == len(parts) - 1
            if part not in current:
                current[part] = {"is_file": is_file, "children": {}}
            if not is_file:
                current = current[part]["children"]

    lines = ["."]

    def render(node: Dict[str, Any], prefix: str = ""):
        items = sorted(node.items(), key=lambda kv: (kv[1]["is_file"], kv[0].lower()))

        for index, (name, meta) in enumerate(items):
            is_last = index == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + name)
            if meta["children"]:
                new_prefix = prefix + ("    " if is_last else "│   ")
                render(meta["children"], new_prefix)

    render(root)
    return "\n".join(lines)
