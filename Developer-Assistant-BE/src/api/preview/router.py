# src/api/preview/router.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.preview.manager import start_preview
from src.utils.auth import get_current_user

router = APIRouter(prefix="/preview", tags=["preview"])


class PreviewResponse(BaseModel):
    url: str
    port: int


@router.post("/{run_id}", response_model=PreviewResponse)
def create_preview(run_id: str, user: str = Depends(get_current_user)):
    try:
        state = start_preview(run_id, user, keep=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    url = f"http://localhost:{state.port}/"
    print(f"Preview started for run {run_id} at {url}")
    return PreviewResponse(url=url, port=state.port)

@router.post("/{run_id}/reload", response_model=PreviewResponse)
def reload_preview(run_id: str, user: str = Depends(get_current_user)):
    try:
        state = start_preview(run_id, user, keep=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    url = f"http://localhost:{state.port}/"
    print(f"Preview started for run {run_id} at {url}")
    return PreviewResponse(url=url, port=state.port)
