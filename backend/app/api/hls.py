import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.play import base_url, playable_item, stream_url
from app.db import get_session
from app.services import player, transcode

router = APIRouter()

NAME = re.compile(r"^(?:index\.m3u8|seg_\d{5}\.ts)$")


class StatusOut(BaseModel):
    available: bool
    ffmpeg: str | None


class HlsIn(BaseModel):
    start: float = Field(default=0, ge=0, le=60 * 60 * 24)


class HlsOut(BaseModel):
    mode: str
    duration: float | None
    session_id: str | None = None
    playlist_url: str | None = None
    direct_url: str | None = None


@router.get("/transcode/status")
def status(session: Session = Depends(get_session)) -> StatusOut:
    found = transcode.find_binaries(session)
    return StatusOut(available=found is not None, ffmpeg=found[0] if found else None)


@router.post("/play/{item_id}/hls")
async def start_hls(
    item_id: int,
    request: Request,
    body: HlsIn | None = None,
    session: Session = Depends(get_session),
) -> HlsOut:
    binaries = transcode.find_binaries(session)
    if binaries is None:
        raise HTTPException(503, "找不到 ffmpeg，請安裝或在設定填入路徑")
    ffmpeg, ffprobe = binaries
    _, path = playable_item(session, item_id)
    start = body.start if body else 0
    try:
        info = await transcode.probe(ffprobe, path)
        mode, audio_mode = transcode.decide(info, path.suffix)
        raw = info.get("format", {}).get("duration")
        duration = float(raw) if raw else None
        if mode == "direct" and start == 0:
            url = stream_url(
                base_url(request, session), item_id, path.name, player.get_token(session)
            )
            return HlsOut(mode=mode, duration=duration, direct_url=url)
        if mode == "direct":
            mode, audio_mode = "remux", "copy" if audio_mode == "copy" else "aac"
        sess = await transcode.start_session(
            ffmpeg, item_id, path, mode, audio_mode, start
        )
    except transcode.TranscodeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return HlsOut(
        mode=sess.mode,
        duration=duration,
        session_id=sess.id,
        playlist_url=f"/api/hls/{sess.id}/index.m3u8",
    )


def _session(sid: str) -> transcode.HlsSession:
    sess = transcode.sessions.get(sid)
    if sess is None:
        raise HTTPException(404, "播放工作階段不存在或已結束")
    return sess


@router.get("/hls/{sid}/{name}")
def hls_file(sid: str, name: str) -> FileResponse:
    sess = _session(sid)
    if not NAME.match(name):
        raise HTTPException(404, "檔案不存在")
    path: Path = sess.dir / name
    if not path.is_file():
        raise HTTPException(404, "檔案尚未產生")
    sess.last_access = time.monotonic()
    if name.endswith(".m3u8"):
        return FileResponse(
            path, media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "no-store"},
        )
    return FileResponse(path, media_type="video/mp2t")


@router.post("/hls/{sid}/keepalive")
def keepalive(sid: str) -> dict[str, bool]:
    _session(sid).last_access = time.monotonic()
    return {"ok": True}


@router.delete("/hls/{sid}", status_code=204)
async def stop(sid: str) -> None:
    await transcode.stop_session(sid)
