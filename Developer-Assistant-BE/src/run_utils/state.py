from typing import Any, Dict

RUNS: Dict[str, Dict[str, Any]] = {}

def delete_run(run_id: str) -> None:
    if run_id in RUNS:
        del RUNS[run_id]

def create_run(run_id: str) -> None:
    RUNS[run_id] = {"files": {}, "state": {}}

def get_run(run_id: str) -> Dict[str, Any]:
    r = RUNS.setdefault(run_id, {})
    r.setdefault("files", {})
    return r


def set_run_field(run_id: str, field: str, value: Any) -> None:
    r = get_run(run_id)
    r[field] = value
