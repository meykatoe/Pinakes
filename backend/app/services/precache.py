import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.db import get_engine
from app.models import MediaItem
from app.services import fileops, hwaccel, organizer, settings_store, transcode

queue: asyncio.Queue | None = None
loop: asyncio.AbstractEventLoop | None = None
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


def touch(item_id: int) -> None:
    """記錄最近播放時間。"""
    try:
        os.utime(cache_dir(item_id) / "meta.json")
    except OSError:
        pass


def entries() -> list[tuple[float, int, int]]:
    rows = []
    for folder in cache_root().glob("*"):
        meta = folder / "meta.json"
        if not folder.name.isdigit() or not meta.is_file():
            continue
        size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
        rows.append((meta.stat().st_mtime, int(folder.name), size))
    return sorted(rows)


def evict(max_bytes: int, keep: int | None = None) -> int:
    """超過容量時，由最久沒看的開始清除。"""
    rows = entries()
    total = sum(size for _, _, size in rows)
    removed = 0
    for _, item_id, size in rows:
        if total <= max_bytes:
            break
        if item_id == keep:
            continue
        remove(item_id)
        total -= size
        removed += 1
    return removed


def remove(item_id: int) -> None:
    shutil.rmtree(cache_dir(item_id), ignore_errors=True)


def _lower_priority() -> None:
    os.nice(10)


def _priority_args() -> dict:
    """各平台降低程序優先權的參數。"""
    if sys.platform == "win32":
        return {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS}
    return {"preexec_fn": _lower_priority}


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
                **_priority_args(),
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


def request(session: Session, item_id: int) -> None:
    """整理完成後排入預轉碼，可在其他執行緒呼叫。"""
    if loop is None or settings_store.get_value(session, "precache_enabled") != "true":
        return
    loop.call_soon_threadsafe(enqueue, item_id)


def enqueue(item_id: int) -> bool:
    if queue is None or item_id in queued:
        return False
    queued.add(item_id)
    queue.put_nowait(item_id)
    return True


def _prepare(item_id: int) -> tuple[str, str, Path, str, int] | None:
    with Session(get_engine()) as session:
        item = session.get(MediaItem, item_id)
        binaries = transcode.find_binaries(session)
        if item is None or item.status != "done" or not item.target_path or not binaries:
            return None
        try:
            _, library = organizer.get_roots(session)
            path = Path(item.target_path)
            fileops.ensure_within(path, library)
        except (organizer.OrganizeError, fileops.FileOpError):
            return None
        if not path.is_file():
            return None
        try:
            gb = float(settings_store.get_value(session, "precache_max_gb"))
        except ValueError:
            gb = 50
        pref = settings_store.get_value(session, "hwaccel")
        return binaries[0], binaries[1], path, pref, int(gb * 1024**3)


async def run_item(item_id: int) -> None:
    prepared = await asyncio.to_thread(_prepare, item_id)
    if prepared is None:
        return
    ffmpeg, ffprobe, path, pref, max_bytes = prepared
    if await precache(ffmpeg, ffprobe, item_id, path, pref):
        await asyncio.to_thread(evict, max_bytes, item_id)


async def worker(run=run_item) -> None:
    """依序處理佇列。"""
    global queue, current, loop
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
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
        loop = None
        queued.clear()
