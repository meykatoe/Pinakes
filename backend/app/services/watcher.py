import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlmodel import Session

from app.db import get_engine
from app.models import MediaItem
from app.services import clients, mailer, organizer, scraper, settings_store
from app.services.tmdb import TmdbError

MIN_INTERVAL = 5


class StabilityTracker:
    def __init__(self) -> None:
        self._seen: dict[Path, tuple[int, int, float]] = {}

    def reset(self) -> None:
        self._seen = {}

    @property
    def waiting(self) -> int:
        return len(self._seen)

    def update(self, paths: list[Path], now: float, stable_seconds: int) -> list[Path]:
        current: dict[Path, tuple[int, int, float]] = {}
        stable = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            sig = (stat.st_size, int(stat.st_mtime))
            prev = self._seen.get(path)
            since = prev[2] if prev and prev[:2] == sig else now
            current[path] = (*sig, since)
            if now - since >= stable_seconds and now - stat.st_mtime >= stable_seconds:
                stable.append(path)
        self._seen = current
        return stable


@dataclass
class WatchStatus:
    running: bool = False
    last_run: float | None = None
    last_error: str = ""
    waiting: int = 0
    last_mail_error: str = ""
    last_processed: list[dict] = field(default_factory=list)


status = WatchStatus()


def _execute_in_thread(item_id: int) -> str:
    with Session(get_engine()) as session:
        item = session.get(MediaItem, item_id)
        try:
            return organizer.execute_item(session, item).status
        except organizer.OrganizeError:
            return "failed"


async def run_cycle(
    session: Session,
    tracker: StabilityTracker,
    now: float,
    make_tmdb=clients.build_tmdb,
    make_ai=clients.build_ai,
) -> list[dict]:
    inbox, library = organizer.get_roots(session)
    stable_seconds = int(settings_store.get_value(session, "stable_seconds"))
    candidates = organizer.new_paths(session, inbox)
    stable = tracker.update(candidates, now, stable_seconds)
    status.waiting = tracker.waiting - len(stable)
    if not stable:
        return []
    items = await organizer.plan_paths(
        session, make_tmdb(session), make_ai(session), inbox, library, stable
    )
    auto = settings_store.get_value(session, "auto_execute") == "true"
    results = []
    for item in items:
        state = item.status
        if state == "planned" and auto:
            state = await asyncio.to_thread(_execute_in_thread, item.id)
        session.refresh(item)
        target = Path(item.target_path) if item.target_path else None
        results.append(
            {
                "id": item.id,
                "source": Path(item.source_path).name,
                "status": state,
                "target": str(target.relative_to(library)) if target else "",
                "error": item.error,
                "reason": item.reason,
            }
        )
    return results


async def send_digest(session: Session, results: list[dict]) -> None:
    try:
        await mailer.notify(session, results)
        status.last_mail_error = ""
    except mailer.MailError as exc:
        status.last_mail_error = str(exc)


async def scrape_new(session: Session) -> None:
    try:
        await scraper.scrape_missing(session, clients.build_tmdb(session))
    except TmdbError:
        return


async def watch_loop() -> None:
    tracker = StabilityTracker()
    status.running = True
    try:
        while True:
            interval = MIN_INTERVAL
            try:
                with Session(get_engine()) as session:
                    if settings_store.get_value(session, "watch_enabled") == "true":
                        interval = max(
                            MIN_INTERVAL,
                            int(settings_store.get_value(session, "watch_interval")),
                        )
                        done = await run_cycle(session, tracker, time.time())
                        status.last_run = time.time()
                        status.last_error = ""
                        if done:
                            status.last_processed = done
                            await send_digest(session, done)
                            await scrape_new(session)
                    else:
                        tracker.reset()
                        status.waiting = 0
            except asyncio.CancelledError:
                raise
            except (TmdbError, organizer.OrganizeError, ValueError, OSError) as exc:
                status.last_error = str(exc)
            except Exception as exc:  # noqa: BLE001
                status.last_error = f"未預期錯誤：{exc.__class__.__name__}"
            await asyncio.sleep(interval)
    finally:
        status.running = False


@contextlib.asynccontextmanager
async def background():
    task = asyncio.create_task(watch_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
