from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import MediaItem
from app.services import precache, transcode

router = APIRouter(prefix="/precache")


class StatusOut(BaseModel):
    queued: int
    current: int | None
    cached: int
    bytes: int


class RunOut(BaseModel):
    added: int


@router.get("/status")
def status() -> StatusOut:
    rows = precache.entries()
    return StatusOut(
        queued=len(precache.queued), current=precache.current,
        cached=len(rows), bytes=sum(size for _, _, size in rows),
    )


@router.post("/run")
async def run(session: Session = Depends(get_session)) -> RunOut:
    if transcode.find_binaries(session) is None:
        raise HTTPException(503, "找不到 ffmpeg，請安裝或在設定填入路徑")
    if precache.queue is None:
        raise HTTPException(503, "預轉碼服務尚未啟動")
    ids = session.exec(
        select(MediaItem.id).where(MediaItem.status == "done").order_by(MediaItem.id)
    )
    return RunOut(added=sum(precache.enqueue(i) for i in ids))
