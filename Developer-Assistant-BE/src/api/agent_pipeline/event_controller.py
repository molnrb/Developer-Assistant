from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Body, Depends, Request, Query, HTTPException, status
from fastapi.responses import StreamingResponse

from src.modify.modify_core import run_modify_loop
from src.generate.project_core import run_agentic_loop
from src.run_utils.artifacts import stream_zip_response
from src.run_utils.events import hub
from src.run_utils.report import build_report
from src.run_utils.state import get_run, delete_run, create_run
from src.run_utils.store import list_runs, update_run
from src.utils.auth import get_current_user

router = APIRouter()


@router.post("/runs")
async def create_run(user: str = Depends(get_current_user)):
    import uuid

    run_id = str(uuid.uuid4())
    await hub.emit(run_id, {"t": "status", "step": "router", "state": "queued"})
    return {"run_id": run_id}

def decode_token(token: str) -> str:
   return get_current_user(token)

async def get_current_user_from_query(token: str = Query(...)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    try:
        user = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user

@router.get("/runs/{run_id}/events")
async def stream_events(
    run_id: str,
    request: Request,
    user: str = Depends(get_current_user_from_query),
):
    q = await hub.subscribe(run_id)

    async def heartbeats():
        while True:
            await asyncio.sleep(15)
            try:
                await q.put(": ping\n\n")
            except Exception:
                break

    async def gen():
        hb_task = asyncio.create_task(heartbeats())
        try:
            while True:
                if await request.is_disconnected():
                    break
                chunk: str = await q.get()
                yield chunk.encode("utf-8")
        finally:
            hb_task.cancel()
            hub.unsubscribe(run_id, q)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


@router.post("/runs/{run_id}/start")
async def start_run(
    run_id: str, payload: dict = Body(...), user: str = Depends(get_current_user)
):
    hub.clear(run_id)
    desc = (payload or {}).get("description", "").strip()
    override = (payload or {}).get("domainOverride", "auto")
    planning_model = (payload or {}).get("planningModel", "auto")
    implementer_model = (payload or {}).get("implementerModel", "auto")
    fixer_model = (payload or {}).get("fixerModel", "auto")
    asyncio.create_task(run_agentic_loop(run_id, desc, override, planning_model, implementer_model, fixer_model, user))
    return {"ok": True, "started": True}


@router.get("/runs/{run_id}/files")
async def get_files(run_id: str, user: str = Depends(get_current_user)):
    r = get_run(run_id)

    return {"files": r.get("files", {})}


@router.get("/runs/{run_id}/report")
async def get_report(run_id: str, user: str = Depends(get_current_user)):
    return build_report(run_id)


@router.get("/runs/{run_id}/artifact.zip")
async def get_artifact(run_id: str, user: str = Depends(get_current_user)):
    return stream_zip_response(run_id, user)


@router.get("/runs")
async def runs_index(user: str = Depends(get_current_user)):
    return {"runs": list_runs()}


@router.get("/runs/{run_id}/telemetry")
async def run_telemetry(run_id: str, user: str = Depends(get_current_user)):
    r = get_run(run_id)
    return {
        "id": run_id,
        "status": (r.get("metrics", {}).get("test", {}).get("ok") and "passed")
        or "running",
        "steps": r.get("history", {}).get("steps", []),
        "metrics": r.get("metrics", {}),
        "tokens": r.get("tokens", {}),
        "planCount": len((r.get("plan", {}) or {}).get("files", [])) if r.get("plan") else len(r.get("modify", {}).get("changes", [])),
        "filesCount": len(r.get("files", {})),
    }


async def mark_done(run_id: str, ok: bool):
    update_run(run_id, status="passed" if ok else "failed", finished=time.time())


@router.post("/runs/{run_id}/kill")
async def kill_run(run_id: str, user: str = Depends(get_current_user)):
    """
    Kill a running process (best-effort).
    """
    r = get_run(run_id)
    r["state"]["current"] = "STOP"
    return {"ok": True, "kill_requested": True}


@router.post("/runs/{project_id}/modify")
async def create_modify_run(
    project_id: str, payload: dict = Body(...), user: str = Depends(get_current_user)
):
    """
    Starts a prompt-based modification run for an existing project.
    Body: { "prompt": "Add edit to todos" }
    """
    prompt = (payload or {}).get("prompt", "").strip()
    run_id = project_id
    hub.clear(run_id)
    asyncio.create_task(run_modify_loop(run_id, prompt, user))
    return {"run_id": run_id}
