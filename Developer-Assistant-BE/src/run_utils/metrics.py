import time
from typing import Any, Dict

from src.run_utils.state import get_run


def step_start(run_id: str, name: str):
    r = get_run(run_id)
    m = r.setdefault("metrics", {})
    s = m.setdefault(name, {})
    s["t_start"] = time.time()


def step_end(
    run_id: str, name: str, ok: bool | None = None, extra: Dict[str, Any] | None = None
):
    r = get_run(run_id)
    m = r.setdefault("metrics", {})
    s = m.setdefault(name, {})
    s["t_end"] = time.time()
    if ok is not None:
        s["ok"] = bool(ok)
    if extra:
        s.update(extra)


def add_tokens(
    run_id: str, where: str, prompt_tokens: int = 0, completion_tokens: int = 0
):
    r = get_run(run_id)
    t = r.setdefault("tokens", {})
    e = t.setdefault(where, {"prompt": 0, "completion": 0})
    e["prompt"] += int(prompt_tokens)
    e["completion"] += int(completion_tokens)
