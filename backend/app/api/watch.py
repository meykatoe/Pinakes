from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import settings_store, watcher

router = APIRouter()


class WatchOut(BaseModel):
    enabled: bool
    running: bool
    last_run: float | None
    last_error: str
    waiting: int
    last_processed: list[dict]


@router.get("/watch/status")
def watch_status(session: Session = Depends(get_session)) -> WatchOut:
    st = watcher.status
    return WatchOut(
        enabled=settings_store.get_value(session, "watch_enabled") == "true",
        running=st.running,
        last_run=st.last_run,
        last_error=st.last_error,
        waiting=st.waiting,
        last_processed=st.last_processed,
    )
