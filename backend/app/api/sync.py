from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import rclone_sync, settings_store

router = APIRouter()


class SyncOut(BaseModel):
    enabled: bool
    running: bool
    busy: bool
    last_run: float | None
    last_error: str
    last_count: int
    last_failed: int


class SyncRun(BaseModel):
    started: bool


@router.get("/sync/status")
def sync_status(session: Session = Depends(get_session)) -> SyncOut:
    st = rclone_sync.status
    return SyncOut(
        enabled=settings_store.get_value(session, "sync_enabled") == "true",
        running=st.running,
        busy=st.busy,
        last_run=st.last_run,
        last_error=st.last_error,
        last_count=st.last_count,
        last_failed=st.last_failed,
    )


@router.post("/sync/run")
async def sync_run() -> SyncRun:
    return SyncRun(started=rclone_sync.trigger())
