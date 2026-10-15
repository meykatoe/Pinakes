import asyncio
import json
import os
import secrets
import shutil
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.services import settings_store

IDLE_SECONDS = 90
DONE_IDLE_SECONDS = 1800
MAX_SESSIONS = 3
READY_TIMEOUT = 25
PROBE_TIMEOUT = 20
DIRECT_VIDEO = {"h264"}
DIRECT_PIX = {"yuv420p", "yuvj420p"}
MP4_AUDIO = {"aac", "mp3"}
WEBM_VIDEO = {"vp8", "vp9", "av1"}
WEBM_AUDIO = {"opus", "vorbis"}


class TranscodeError(Exception):
    pass


@dataclass
class HlsSession:
    id: str
    item_id: int
    start: float
    mode: str
    dir: Path
    proc: asyncio.subprocess.Process
    last_access: float = field(default_factory=time.monotonic)

    @property
    def running(self) -> bool:
        return self.proc.returncode is None


sessions: dict[str, HlsSession] = {}


def hls_root() -> Path:
    return settings.data_dir / "hls"


def find_binaries(session: Session) -> tuple[str, str] | None:
    custom = settings_store.get_value(session, "ffmpeg_path")
    ffmpeg = custom or shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    if custom:
        probe = str(Path(custom).with_name("ffprobe"))
        probe = probe if os.access(probe, os.X_OK) else shutil.which("ffprobe")
    else:
        probe = shutil.which("ffprobe")
    return (ffmpeg, probe) if probe else None


async def probe(ffprobe: str, path: Path) -> dict:
    proc = await asyncio.create_subprocess_exec(
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), PROBE_TIMEOUT)
    except TimeoutError as exc:
        proc.kill()
        raise TranscodeError("分析影片逾時") from exc
    if proc.returncode != 0:
        raise TranscodeError("無法分析這個影片檔")
    try:
        return json.loads(out)
    except ValueError as exc:
        raise TranscodeError("無法分析這個影片檔") from exc


def decide(info: dict, suffix: str) -> tuple[str, str]:
    """回傳播放模式與音訊處理方式。"""
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise TranscodeError("檔案中沒有影像")
    vcodec = video.get("codec_name", "")
    acodec = audio.get("codec_name", "") if audio else ""
    suffix = suffix.lower()
    h264_ok = vcodec in DIRECT_VIDEO and video.get("pix_fmt") in DIRECT_PIX
    if suffix in (".mp4", ".m4v", ".mov") and h264_ok and (not audio or acodec in MP4_AUDIO):
        return "direct", "copy"
    if suffix == ".webm" and vcodec in WEBM_VIDEO and (not audio or acodec in WEBM_AUDIO):
        return "direct", "copy"
    audio_mode = "copy" if acodec == "aac" else "aac"
    return ("remux" if h264_ok else "transcode"), audio_mode


def build_command(
    ffmpeg: str, path: Path, mode: str, audio_mode: str, start: float, out_dir: Path
) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path), "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn"]
    if mode == "remux":
        cmd += ["-c:v", "copy"]
    else:
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-force_key_frames", "expr:gte(t,n_forced*4)",
        ]
    if audio_mode == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ac", "2"]
    cmd += [
        "-f", "hls", "-hls_time", "4", "-hls_list_size", "0",
        "-hls_playlist_type", "event",
        "-hls_segment_filename", str(out_dir / "seg_%05d.ts"),
        str(out_dir / "index.m3u8"),
    ]
    return cmd


def _log_tail(out_dir: Path) -> str:
    log = out_dir / "ffmpeg.log"
    try:
        return log.read_text(errors="replace").strip()[-300:]
    except OSError:
        return ""


async def _wait_ready(sess: HlsSession) -> None:
    playlist = sess.dir / "index.m3u8"
    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        if playlist.exists() and ".ts" in playlist.read_text(errors="replace"):
            return
        if not sess.running:
            if playlist.exists() and ".ts" in playlist.read_text(errors="replace"):
                return
            detail = _log_tail(sess.dir)
            await stop_session(sess.id)
            raise TranscodeError(f"轉碼失敗：{detail}" if detail else "轉碼失敗")
        await asyncio.sleep(0.2)
    await stop_session(sess.id)
    raise TranscodeError("轉碼逾時")


async def start_session(
    ffmpeg: str, item_id: int, path: Path, mode: str, audio_mode: str, start: float,
) -> HlsSession:
    for sess in sessions.values():
        same = sess.item_id == item_id and abs(sess.start - start) < 0.5
        if same and (sess.running or sess.proc.returncode == 0):
            sess.last_access = time.monotonic()
            return sess
    while len(sessions) >= MAX_SESSIONS:
        oldest = min(sessions.values(), key=lambda s: s.last_access)
        await stop_session(oldest.id)
    sid = secrets.token_urlsafe(16)
    out_dir = hls_root() / sid
    out_dir.mkdir(parents=True)
    cmd = build_command(ffmpeg, path, mode, audio_mode, start, out_dir)
    log = open(out_dir / "ffmpeg.log", "wb")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL, stderr=log,
        )
    except OSError as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise TranscodeError(f"無法啟動 ffmpeg：{exc.strerror}") from exc
    finally:
        log.close()
    sess = HlsSession(sid, item_id, start, mode, out_dir, proc)
    sessions[sid] = sess
    await _wait_ready(sess)
    return sess


async def stop_session(sid: str) -> bool:
    sess = sessions.pop(sid, None)
    if sess is None:
        return False
    if sess.running:
        sess.proc.terminate()
        try:
            await asyncio.wait_for(sess.proc.wait(), 5)
        except TimeoutError:
            sess.proc.kill()
            await sess.proc.wait()
    shutil.rmtree(sess.dir, ignore_errors=True)
    return True


async def reap_once(now: float | None = None) -> int:
    now = time.monotonic() if now is None else now
    stale = [
        s.id for s in sessions.values()
        if now - s.last_access > (IDLE_SECONDS if s.running else DONE_IDLE_SECONDS)
    ]
    for sid in stale:
        await stop_session(sid)
    return len(stale)


async def stop_all() -> None:
    for sid in list(sessions):
        await stop_session(sid)


def kill_all_sync() -> None:
    for sess in list(sessions.values()):
        try:
            os.kill(sess.proc.pid, signal.SIGKILL)
        except OSError:
            pass
        shutil.rmtree(sess.dir, ignore_errors=True)
    sessions.clear()


def clean_orphans() -> None:
    shutil.rmtree(hls_root(), ignore_errors=True)


async def reaper() -> None:
    clean_orphans()
    try:
        while True:
            await asyncio.sleep(15)
            await reap_once()
    finally:
        await stop_all()
