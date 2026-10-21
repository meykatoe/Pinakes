import asyncio
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col, select

from app.models import Category, MediaItem, OperationLog
from app.services import (
    fileops,
    matcher,
    naming,
    nfo,
    pipeline,
    precache,
    settings_store,
)
from app.services.fileops import FileOpError
from app.services.parser import VIDEO_EXTS
from app.services.tmdb import TmdbClient

SUB_EXTS = {".srt", ".ass", ".ssa", ".sub", ".vtt", ".idx"}
SAMPLE = re.compile(r"(?<![a-z])sample(?![a-z])", re.I)
execute_lock = threading.Lock()
# 避免重複掃描
scan_lock = asyncio.Lock()


class OrganizeError(Exception):
    pass


@dataclass
class Progress:
    running: bool = False
    done: int = 0
    total: int = 0
    current: str = ""


progress = Progress()


def _now() -> datetime:
    return datetime.now(UTC)


def get_roots(session: Session) -> tuple[Path, Path]:
    inbox = settings_store.get_value(session, "inbox_path")
    lib = settings_store.get_value(session, "library_path")
    if not inbox or not lib:
        raise OrganizeError("尚未設定待整理與已整理目錄")
    inbox_p, lib_p = Path(inbox), Path(lib)
    if not inbox_p.is_dir() or not lib_p.is_dir():
        raise OrganizeError("待整理或已整理目錄不存在")
    return inbox_p, lib_p


def find_videos(inbox: Path) -> list[Path]:
    found = []
    for root, dirs, files in os.walk(inbox, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            path = Path(root) / name
            if path.suffix.lower() not in VIDEO_EXTS or path.is_symlink():
                continue
            if SAMPLE.search(path.stem):
                continue
            found.append(path)
    return found


def is_known(session: Session, path: Path) -> bool:
    stat = path.stat()
    stmt = select(MediaItem).where(
        MediaItem.source_path == str(path),
        MediaItem.size == stat.st_size,
        MediaItem.mtime == int(stat.st_mtime),
    )
    return session.exec(stmt).first() is not None


def new_paths(session: Session, inbox: Path) -> list[Path]:
    return [p for p in find_videos(inbox) if not is_known(session, p)]


async def plan_paths(
    session: Session,
    client: TmdbClient,
    ai,
    inbox: Path,
    library: Path,
    paths: list[Path],
    track: bool = False,
) -> list[MediaItem]:
    if track:
        progress.running, progress.done, progress.total = True, 0, len(paths)
    try:
        return await _plan_all(session, client, ai, inbox, library, paths, track)
    finally:
        if track:
            progress.running, progress.current = False, ""


async def _plan_all(
    session, client, ai, inbox, library, paths, track
) -> list[MediaItem]:
    items = []
    for path in paths:
        if track:
            progress.current = path.name
        try:
            stat = path.stat()
        except OSError:
            continue
        item = MediaItem(
            source_path=str(path), size=stat.st_size, mtime=int(stat.st_mtime)
        )
        try:
            await plan_item(session, client, ai, item, inbox, library)
        except (OrganizeError, ValueError) as exc:
            item.status, item.error = "failed", str(exc)
            session.add(item)
            session.commit()
        items.append(item)
        if track:
            progress.done += 1
    return items


def pick_category(session: Session, item: MediaItem) -> Category:
    if item.category_id:
        cat = session.get(Category, item.category_id)
        if cat and cat.media_type == item.media_type:
            return cat
    stmt = (
        select(Category)
        .where(Category.media_type == item.media_type)
        .order_by(Category.id)
    )
    cat = session.exec(stmt).first()
    if cat is None:
        raise OrganizeError("找不到對應的分類")
    return cat


def find_companions(src: Path, dst: Path) -> list[dict]:
    result = []
    prefix = src.stem + "."
    for sibling in sorted(src.parent.iterdir()):
        if (
            sibling.is_file()
            and not sibling.is_symlink()
            and sibling.suffix.lower() in SUB_EXTS
            and sibling.name.startswith(prefix)
        ):
            tail = sibling.name[len(src.stem) :]
            result.append(
                {"src": str(sibling), "dst": str(dst.with_name(dst.stem + tail))}
            )
    return result


async def compute_target(
    session: Session,
    client: TmdbClient,
    item: MediaItem,
    chosen: matcher.Candidate,
    library: Path,
    inbox: Path,
) -> None:
    src = Path(item.source_path)
    parsed = pipeline.parse_file(session, list(src.relative_to(inbox).parts))
    parsed.media_type = chosen.media_type
    if chosen.media_type == "tv" and parsed.season is None:
        parsed.season = 1
    values = await matcher.build_values(client, parsed, chosen)
    key = "tv_template" if chosen.media_type == "tv" else "movie_template"
    rel = naming.render(settings_store.get_value(session, key), values, parsed.ext)
    item.media_type = chosen.media_type
    item.tmdb_id = chosen.tmdb_id
    item.title = chosen.title
    item.year = chosen.year
    item.season, item.episode = parsed.season, parsed.episode
    category = pick_category(session, item)
    item.category_id = category.id
    target = library / category.subdir / rel
    fileops.ensure_within(target, library)
    item.target_path = str(target)
    item.companions = json.dumps(find_companions(src, target), ensure_ascii=False)


async def plan_item(
    session: Session,
    client: TmdbClient,
    ai,
    item: MediaItem,
    inbox: Path,
    library: Path,
    forced: matcher.Candidate | None = None,
) -> None:
    src = Path(item.source_path)
    parsed = pipeline.parse_file(session, list(src.relative_to(inbox).parts))
    item.media_type = parsed.media_type
    item.error = ""
    if forced is not None:
        res = matcher.Resolution([forced], forced, "manual")
    else:
        res = await matcher.resolve(client, ai, parsed, src.name)
    item.method, item.reason = res.method, res.reason
    item.candidates = json.dumps(
        [c.model_dump() for c in res.candidates], ensure_ascii=False
    )
    item.mode = settings_store.get_value(session, "organize_mode")
    review_ai = (
        res.method == "ai"
        and settings_store.get_value(session, "ai_auto_apply") != "true"
    )
    if res.chosen is None:
        item.status = "pending_review"
    else:
        await compute_target(session, client, item, res.chosen, library, inbox)
        item.status = "pending_review" if review_ai else "planned"
    item.updated_at = _now()
    session.add(item)
    session.commit()


def _log(session: Session, item: MediaItem, action, src, dst, backup="") -> OperationLog:
    row = OperationLog(
        item_id=item.id, action=action, src=str(src), dst=str(dst), backup=str(backup)
    )
    session.add(row)
    session.commit()
    return row


def _place_one(
    session: Session,
    item: MediaItem,
    src: Path,
    dst: Path,
    library: Path,
    policy: str,
    stamp: str,
    logs: list[OperationLog],
) -> bool:
    fileops.ensure_within(dst, library)
    backup = ""
    if fileops.exists(dst):
        if dst.exists() and os.path.samefile(src, dst):
            return True
        if policy == "skip":
            return False
        if policy == "keep_larger" and src.stat().st_size <= dst.stat().st_size:
            return False
        backup = str(fileops.backup_existing(dst, library, stamp))
    try:
        fileops.place(item.mode, src, dst)
    except FileOpError:
        if backup:
            os.replace(backup, dst)
        raise
    logs.append(_log(session, item, item.mode, src, dst, backup))
    return True


def _prune_sources(src: Path, companions: str, inbox: Path) -> None:
    dirs = {src.parent, *(Path(c["src"]).parent for c in json.loads(companions))}
    for folder in dirs:
        fileops.prune_empty(folder, inbox)


def execute_item(session: Session, item: MediaItem) -> MediaItem:
    with execute_lock:
        if item.status not in ("planned", "failed"):
            raise OrganizeError("此項目目前無法執行")
        inbox, library = get_roots(session)
        policy = settings_store.get_value(session, "conflict_policy")
        stamp = _now().strftime("%Y%m%d-%H%M%S")
        logs: list[OperationLog] = []
        try:
            src = Path(item.source_path)
            fileops.ensure_within(src, inbox)
            if not src.is_file() or src.is_symlink():
                raise FileOpError("來源檔案不存在")
            dst = Path(item.target_path)
            if not _place_one(session, item, src, dst, library, policy, stamp, logs):
                item.status, item.reason = "skipped", "目標已存在，依設定略過"
            else:
                for comp in json.loads(item.companions):
                    csrc = Path(comp["src"])
                    if csrc.is_file():
                        _place_one(
                            session, item, csrc, Path(comp["dst"]), library,
                            policy, stamp, logs,
                        )
                item.status, item.error = "done", ""
                if item.mode == "move":
                    _prune_sources(src, item.companions, inbox)
        except (FileOpError, OSError) as exc:
            _rollback(session, logs, library)
            item.status, item.error = "failed", str(exc)
        item.updated_at = _now()
        session.add(item)
        session.commit()
        if item.status == "done":
            precache.request(session, item.id)
        return item


def _rollback(session: Session, logs: list[OperationLog], library: Path) -> None:
    for log in reversed(logs):
        try:
            fileops.revert(log.action, Path(log.src), Path(log.dst), log.backup, library)
        except FileOpError:
            continue
        session.delete(log)
    session.commit()


def _hand_over(session: Session, item: MediaItem, log: OperationLog) -> bool:
    # 共用檔轉給同目錄其他項目
    if Path(log.dst).name not in nfo.SHARED:
        return False
    prefix = str(Path(log.dst).parent) + os.sep
    stmt = select(MediaItem).where(
        MediaItem.status == "done",
        MediaItem.id != item.id,
        col(MediaItem.target_path).startswith(prefix),
    )
    other = session.exec(stmt).first()
    if other is None:
        return False
    log.item_id = other.id
    session.add(log)
    session.commit()
    return True


def undo_item(session: Session, item: MediaItem) -> MediaItem:
    with execute_lock:
        if item.status != "done":
            raise OrganizeError("只有已完成的項目可以還原")
        _, library = get_roots(session)
        stmt = (
            select(OperationLog)
            .where(OperationLog.item_id == item.id, OperationLog.undone == False)  # noqa: E712
            .order_by(OperationLog.id.desc())
        )
        for log in list(session.exec(stmt)):
            if log.action == "nfo" and _hand_over(session, item, log):
                continue
            try:
                fileops.revert(
                    log.action, Path(log.src), Path(log.dst), log.backup, library
                )
            except FileOpError as exc:
                item.error = f"還原失敗：{exc}"
                session.add(item)
                session.commit()
                raise OrganizeError(item.error) from exc
            log.undone = True
            session.add(log)
            session.commit()
        item.status, item.error = "undone", ""
        item.updated_at = _now()
        session.add(item)
        session.commit()
        return item
