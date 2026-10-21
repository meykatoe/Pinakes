import asyncio
import json
import os
import shutil
from pathlib import Path

from app.config import settings
from app.services import hwaccel, transcode

queue: asyncio.Queue | None = None
queued: set[int] = set()
current: int | None = None


def cache_root() -> Path:
    return settings.data_dir / "cache"


def cache_dir(item_id: int) -> Path:
    return cache_root() / str(item_id)


def _stamp(path: Path) -> dict[str, int]:
    st = path.stat()
    return {"size": st.st_size, "mtime": int(st.st_mtime)}


def is_cached(item_id: int, path: Path) -> bool:
    """快取完整且來源檔未變動。"""
    meta = cache_dir(item_id) / "meta.json"
    try:
        saved = json.loads(meta.read_text())
        return saved == _stamp(path) and (cache_dir(item_id) / "index.m3u8").is_file()
    except (OSError, ValueError):
        return False


def remove(item_id: int) -> None:
    shutil.rmtree(cache_dir(item_id), ignore_errors=True)


def _lower_priority() -> None:
    os.nice(10)


async def precache(
    ffmpeg: str, ffprobe: str, item_id: int, path: Path, hw_pref: str = "off",
) -> bool:
    """轉成可直接播放的快取，不需轉碼的檔案會略過。"""
    if is_cached(item_id, path):
        return True
    info = await transcode.probe(ffprobe, path)
    mode, audio_mode = transcode.decide(info, path.suffix)
    if mode == "direct":
        return False
    stamp = _stamp(path)
    final = cache_dir(item_id)
    tmp = cache_root() / f"{item_id}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    hw = await asyncio.to_thread(hwaccel.detect, ffmpeg, hw_pref)
    cmd = transcode.build_command(ffmpeg, path, mode, audio_mode, 0, tmp, hw)
    try:
        with open(tmp / "ffmpeg.log", "wb") as log:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, stderr=log,
                preexec_fn=_lower_priority,
            )
            try:
                code = await proc.wait()
            except asyncio.CancelledError:
                proc.kill()
                await proc.wait()
                raise
    except OSError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        raise transcode.TranscodeError(f"無法啟動 ffmpeg：{exc.strerror}") from exc
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if code != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise transcode.TranscodeError("預轉碼失敗")
    (tmp / "ffmpeg.log").unlink(missing_ok=True)
    (tmp / "meta.json").write_text(json.dumps(stamp))
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    return True


def enqueue(item_id: int) -> bool:
    if queue is None or item_id in queued:
        return False
    queued.add(item_id)
    queue.put_nowait(item_id)
    return True


async def worker(run) -> None:
    """依序處理佇列，run 負責取得路徑並轉碼。"""
    global queue, current
    queue = asyncio.Queue()
    try:
        while True:
            item_id = await queue.get()
            current = item_id
            try:
                await run(item_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            finally:
                queued.discard(item_id)
                current = None
    finally:
        queue = None
        queued.clear()
