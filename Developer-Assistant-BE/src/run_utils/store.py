import time
import uuid

DB: dict[str, dict] = {}


def new_run(desc: str):
    rid = str(uuid.uuid4())
    DB[rid] = {
        "id": rid,
        "created": time.time(),
        "description": desc,
        "status": "running",
    }
    return DB[rid]

def new_run_with_id(rid: str):
    DB = {}
    DB[rid] = {
        "id": rid,
        "created": time.time(),
        "status": "running",
    }
    return DB[rid]

def get_run_doc(rid: str):
    return DB.get(rid, {})


def update_run(rid: str, **kw):
    DB[rid].update(kw)


def list_runs(limit=50):
    return sorted(DB.values(), key=lambda r: r["created"], reverse=True)[:limit]
