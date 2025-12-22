from typing import Any, Dict

from src.run_utils.state import get_run


def build_report(run_id: str) -> Dict[str, Any]:
    r = get_run(run_id)
    plan = r.get("plan", {})
    router = r.get("router", {})
    metrics = r.get("metrics", {})
    tokens = r.get("tokens", {})
    tests = {
        "compile_passed": r.get("last_tsc_log") is not None
        and metrics.get("test", {}).get("ok")
    }
    return {
        "runId": run_id,
        "description": r.get("description", ""),
        "domain": router.get("domain"),
        "router": router,
        "plan": {
            "fileCount": len(plan.get("files", [])),
            "style": plan.get("style"),
            "summary": plan.get("summary"),
        },
        "metrics": metrics, 
        "tokens": tokens, 
        "tests": tests,
        "filesCount": len(r.get("files", {})),
    }
