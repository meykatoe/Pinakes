import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session

from app.api.play import playable_item
from app.db import get_session
from app.services import transcode

router = APIRouter()

SUB_EXTS = {".srt", ".ass", ".ssa", ".vtt"}
CONVERT_TIMEOUT = 30


class SubOut(BaseModel):
    index: int
    label: str


def find_subs(video: Path) -> list[Path]:
    prefix = video.stem + "."
    found = [
        p for p in video.parent.iterdir()
        if p.is_file() and p.suffix.lower() in SUB_EXTS and p.name.startswith(prefix)
    ]
    return sorted(found)


def label_of(video: Path, sub: Path) -> str:
    tail = sub.name[len(video.stem) + 1 : -len(sub.suffix)]
    return tail or sub.suffix.lstrip(".").upper()


@router.get("/play/{item_id}/subtitles")
def list_subtitles(item_id: int, session: Session = Depends(get_session)) -> list[SubOut]:
    _, path = playable_item(session, item_id)
    return [SubOut(index=i, label=label_of(path, s)) for i, s in enumerate(find_subs(path))]


CUE = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3}) --> (?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})(.*)$")


def _fmt(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}"


def _secs(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def shift_vtt(text: str, offset: float) -> str:
    blocks = re.split(r"\n\n+", text.strip())
    out = [blocks[0]]
    for block in blocks[1:]:
        lines = block.split("\n")
        for i, line in enumerate(lines):
            m = CUE.match(line)
            if not m:
                continue
            start = _secs(*m.group(1, 2, 3, 4)) - offset
            end = _secs(*m.group(5, 6, 7, 8)) - offset
            if end <= 0:
                lines = []
            else:
                lines[i] = f"{_fmt(max(start, 0))} --> {_fmt(end)}{m.group(9)}"
            break
        if lines:
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "big5", "gb18030", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@router.get("/play/{item_id}/subtitles/{index}.vtt")
async def get_subtitle(
    item_id: int,
    index: int,
    offset: float = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> Response:
    _, path = playable_item(session, item_id)
    subs = find_subs(path)
    if not 0 <= index < len(subs):
        raise HTTPException(404, "字幕不存在")
    binaries = transcode.find_binaries(session)
    if binaries is None:
        raise HTTPException(503, "找不到 ffmpeg")
    text = _decode(subs[index].read_bytes())
    cmd = [binaries[0], "-hide_banner", "-loglevel", "error", "-sub_charenc", "UTF-8"]
    cmd += ["-f", subs[index].suffix.lstrip(".").lower().replace("ssa", "ass"), "-i", "pipe:0",
            "-f", "webvtt", "pipe:1"]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(text.encode()), CONVERT_TIMEOUT)
    except TimeoutError as exc:
        proc.kill()
        raise HTTPException(502, "字幕轉換逾時") from exc
    if proc.returncode != 0 or not out:
        raise HTTPException(502, "無法轉換這個字幕")
    body = shift_vtt(out.decode("utf-8", errors="replace"), offset) if offset else out.decode()
    return Response(body, media_type="text/vtt; charset=utf-8", headers={"Cache-Control": "no-store"})
