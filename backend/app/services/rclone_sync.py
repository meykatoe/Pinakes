import asyncio
import contextlib
import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlmodel import Session, col, delete, select

from app.db import get_engine
from app.models import SyncedFile, SyncFailure
from app.services import clients, organizer, settings_store, watcher
from app.services.parser import VIDEO_EXTS
from app.services.tmdb import TmdbError

TICK = 30
RC_TIMEOUT = 30
log = logging.getLogger("pinakes.sync")


class SyncError(Exception):
    pass


@dataclass
class SyncStatus:
    running: bool = False
    busy: bool = False
    last_run: float | None = None
    last_error: str = ""
    last_count: int = 0
    last_failed: int = 0


status = SyncStatus()
_tasks: set[asyncio.Task] = set()


def get_source(session: Session) -> Path:
    raw = settings_store.get_value(session, "sync_source_path")
    if not raw:
        raise SyncError("尚未設定同步來源資料夾")
    source = Path(raw)
    if not source.is_dir():
        raise SyncError("同步來源資料夾不存在，請確認 rclone 已掛載")
    inbox, library = organizer.get_roots(session)
    for other in (inbox, library):
        if source.resolve() in (other.resolve(), *other.resolve().parents):
            raise SyncError("同步來源不可包含待整理或已整理目錄")
        if other.resolve() in source.resolve().parents:
            raise SyncError("同步來源不可位於待整理或已整理目錄內")
    return source


def scan(source: Path) -> list[Path]:
    found = []
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            path = Path(root) / name
            ext = path.suffix.lower()
            if ext not in VIDEO_EXTS and ext not in organizer.SUB_EXTS:
                continue
            if path.is_symlink() or organizer.SAMPLE.search(path.stem):
                continue
            found.append(path)
    return found


def _synced(session: Session, rel: str, size: int, mtime: int) -> bool:
    stmt = select(SyncedFile).where(
        SyncedFile.rel_path == rel,
        SyncedFile.size == size,
        SyncedFile.mtime == mtime,
    )
    return session.exec(stmt).first() is not None


def pending(
    session: Session, source: Path, now: float, min_age: int
) -> list[tuple[Path, str, int, int]]:
    todo = []
    for path in scan(source):
        try:
            stat = path.stat()
        except OSError:
            continue
        if now - stat.st_mtime < min_age:
            continue
        rel = str(path.relative_to(source))
        mtime = int(stat.st_mtime)
        if not _synced(session, rel, stat.st_size, mtime):
            todo.append((path, rel, stat.st_size, mtime))
    return todo


def _copy(src: Path, part: Path) -> None:
    for attempt in (1, 2):
        part.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, part)
            return
        except FileNotFoundError:
            # 資料夾被清掉時重試
            if attempt == 2 or not src.exists():
                raise
        except OSError:
            part.unlink(missing_ok=True)
            raise


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=RC_TIMEOUT)


async def refresh_mount(url: str) -> None:
    if not url:
        return
    async with make_client() as client:
        try:
            res = await client.post(
                f"{url.rstrip('/')}/vfs/refresh", json={"recursive": "true"}
            )
        except httpx.HTTPError as exc:
            raise SyncError(f"rclone 更新失敗：{exc.__class__.__name__}") from exc
    if res.status_code != 200:
        raise SyncError(f"rclone 更新失敗（HTTP {res.status_code}）")


def _unseen(session: Session, rel: str, size: int, mtime: int) -> bool:
    stmt = select(SyncFailure).where(
        SyncFailure.rel_path == rel,
        SyncFailure.size == size,
        SyncFailure.mtime == mtime,
    )
    return session.exec(stmt).first() is None


def settle_failures(
    session: Session, failed: list[tuple[str, int, int, dict]], ok: list[str]
) -> list[dict]:
    if ok:
        session.exec(delete(SyncFailure).where(col(SyncFailure.rel_path).in_(ok)))
    fresh = []
    for rel, size, mtime, result in failed:
        if _unseen(session, rel, size, mtime):
            session.add(
                SyncFailure(
                    rel_path=rel, size=size, mtime=mtime, error=result["error"]
                )
            )
            fresh.append(result)
    session.commit()
    return fresh


def _result(name: str, state: str, target: str = "", error: str = "") -> dict:
    return {
        "id": 0, "source": name, "status": state,
        "target": target, "error": error, "reason": "",
    }


async def run_cycle(
    session: Session,
    now: float,
    make_tmdb=clients.build_tmdb,
    make_ai=clients.build_ai,
) -> list[dict]:
    source = get_source(session)
    inbox, library = organizer.get_roots(session)
    min_age = int(settings_store.get_value(session, "stable_seconds"))
    notes = []
    status.last_error = ""
    try:
        await refresh_mount(settings_store.get_value(session, "sync_rc_url"))
    except SyncError as exc:
        notes.append(str(exc))
    todo = await asyncio.to_thread(pending, session, source, now, min_age)

    copied, failed = [], []
    for path, rel, size, mtime in todo:
        dest = inbox / rel
        part = dest.with_name(f".{dest.name}.part")
        if dest.exists() and dest.stat().st_size != size:
            failed.append(
                (rel, size, mtime, _result(path.name, "failed", error="待整理目錄已有同名檔案"))
            )
            continue
        try:
            if not dest.exists():
                await asyncio.to_thread(_copy, path, part)
        except OSError as exc:
            failed.append(
                (rel, size, mtime, _result(path.name, "failed", error=f"複製失敗：{exc.strerror}"))
            )
            continue
        copied.append((path, rel, size, mtime, dest, part))

    videos = []
    async with organizer.scan_lock:
        for path, rel, size, mtime, dest, part in copied:
            if part.exists():
                os.replace(part, dest)
            session.add(
                SyncedFile(
                    rel_path=rel, size=size, mtime=mtime, dest_path=str(dest)
                )
            )
            is_video = path.suffix.lower() in VIDEO_EXTS
            if is_video and not organizer.is_known(session, dest):
                videos.append(dest)
        session.commit()
        auto = settings_store.get_value(session, "sync_auto_organize") == "true"
        items = []
        if auto and videos:
            items = await organizer.plan_paths(
                session, make_tmdb(session), make_ai(session), inbox, library,
                videos, track=True,
            )
    status.last_failed = len(failed)
    if auto:
        results = await watcher.finish_items(session, items, library)
    else:
        results = [
            _result(p.name, "synced", str(p.relative_to(inbox))) for p in videos
        ]
    status.last_count = len(results)
    if notes:
        status.last_error = "；".join(notes)
    return results + settle_failures(
        session, failed, [c[1] for c in copied]
    )


async def sync_once(session: Session) -> None:
    status.busy = True
    try:
        done = await run_cycle(session, time.time())
        if done:
            await watcher.send_digest(session, done)
            if any(r["status"] != "failed" for r in done):
                await watcher.scrape_new(session)
    except SyncError as exc:
        status.last_error = str(exc)
    except (TmdbError, organizer.OrganizeError, ValueError, OSError) as exc:
        status.last_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        log.exception("sync cycle failed")
        status.last_error = f"未預期錯誤：{exc.__class__.__name__}"
    finally:
        status.busy = False
        status.last_run = time.time()


def trigger() -> bool:
    if status.busy:
        return False

    async def go() -> None:
        with Session(get_engine()) as session:
            await sync_once(session)

    task = asyncio.create_task(go())
    status.busy = True
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True


def due(session: Session, now: float) -> bool:
    if settings_store.get_value(session, "sync_enabled") != "true":
        return False
    try:
        minutes = max(1, int(settings_store.get_value(session, "sync_interval")))
    except ValueError:
        minutes = 30
    return status.last_run is None or now - status.last_run >= minutes * 60


async def sync_loop() -> None:
    status.running = True
    try:
        while True:
            try:
                with Session(get_engine()) as session:
                    if not status.busy and due(session, time.time()):
                        await sync_once(session)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("sync loop failed")
            await asyncio.sleep(TICK)
    finally:
        status.running = False


@contextlib.asynccontextmanager
async def background():
    task = asyncio.create_task(sync_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
