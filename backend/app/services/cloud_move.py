import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.models import CloudMove, MediaItem, SyncedFile
from app.services import organizer, rclone_sync, settings_store

MAX_TRIES = 5
FS = re.compile(r"^[^:/\\\s]+:.*$")
log = logging.getLogger("pinakes.cloud")


class CloudMoveError(Exception):
    pass


@dataclass
class CloudResult:
    moved: int = 0
    # 檔名、錯誤、是否第一次失敗
    failed: list[tuple[str, str, bool]] = field(default_factory=list)


def normalize_fs(value: str) -> str:
    value = value.strip()
    if value and not value.endswith(":"):
        value = value.rstrip("/")
    return value


def split_fs(value: str) -> tuple[str, str]:
    remote, _, path = value.partition(":")
    return remote, path.strip("/")


def overlaps(a: str, b: str) -> bool:
    ra, pa = split_fs(a)
    rb, pb = split_fs(b)
    if ra != rb:
        return False
    if not pa or not pb:
        return True
    return pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/")


def load_config(session: Session) -> tuple[str, str, str, httpx.BasicAuth | None]:
    def get(key: str) -> str:
        return settings_store.get_value(session, key)

    url = get("sync_rc_url").rstrip("/")
    source, library = get("cloud_source_fs"), get("cloud_library_fs")
    if not url:
        raise CloudMoveError("尚未設定 rclone 遠端控制網址")
    if not (FS.match(source) and FS.match(library)):
        raise CloudMoveError("尚未設定雲端來源與雲端媒體庫")
    if overlaps(source, library):
        raise CloudMoveError("雲端媒體庫不可與雲端來源互相包含")
    return url, source, library, rclone_sync.rc_auth(session)


def plan(session: Session, library: Path) -> list[tuple[int, str, str]]:
    """列出尚需在雲端搬移的檔案：項目編號、雲端相對路徑、媒體庫相對路徑。"""
    synced = {
        row.dest_path: row.rel_path for row in session.exec(select(SyncedFile))
    }
    moves = {
        (row.item_id, row.rel_path): row for row in session.exec(select(CloudMove))
    }
    todo = []
    items = session.exec(select(MediaItem).where(MediaItem.status == "done"))
    for item in items:
        pairs = [(item.source_path, item.target_path)]
        pairs += [(c["src"], c["dst"]) for c in json.loads(item.companions)]
        for src, dst in pairs:
            rel = synced.get(src)
            if rel is None:
                continue
            rel = Path(rel).as_posix()
            row = moves.get((item.id, rel))
            if row and (row.status == "done" or row.tries >= MAX_TRIES):
                continue
            try:
                target = Path(dst).relative_to(library).as_posix()
            except ValueError:
                continue
            todo.append((item.id, rel, target))
    return todo


async def _call(client, url: str, auth, action: str, body: dict) -> dict:
    try:
        res = await client.post(f"{url}/{action}", json=body, auth=auth)
    except httpx.HTTPError as exc:
        raise CloudMoveError(f"無法連線 rclone：{exc.__class__.__name__}") from exc
    if res.status_code != 200:
        try:
            detail = res.json().get("error", "")
        except ValueError:
            detail = ""
        raise CloudMoveError(detail or f"rclone 回應 HTTP {res.status_code}")
    return res.json()


async def _move_one(client, url, auth, source, library, rel: str, dst: str) -> None:
    stat = await _call(
        client, url, auth, "operations/stat", {"fs": library, "remote": dst}
    )
    if stat.get("item"):
        raise CloudMoveError("雲端目標已存在")
    await _call(client, url, auth, "operations/movefile", {
        "srcFs": source, "srcRemote": rel, "dstFs": library, "dstRemote": dst,
    })


def _record(session: Session, item_id: int, rel: str, dst: str, error: str) -> bool:
    stmt = select(CloudMove).where(
        CloudMove.item_id == item_id, CloudMove.rel_path == rel
    )
    row = session.exec(stmt).first() or CloudMove(item_id=item_id, rel_path=rel)
    row.dst, row.updated_at = dst, datetime.now(UTC)
    row.status, row.error = ("failed", error) if error else ("done", "")
    row.tries = row.tries + 1 if error else row.tries
    session.add(row)
    session.commit()
    return row.tries == 1


async def process(session: Session, client=None) -> CloudResult:
    """把已整理項目在雲端對應的原檔搬到整理後路徑。"""
    result = CloudResult()
    if settings_store.get_value(session, "cloud_move_enabled") != "true":
        return result
    url, source, library_fs, auth = load_config(session)
    _, library = organizer.get_roots(session)
    todo = plan(session, library)
    if not todo:
        return result
    async with client or rclone_sync.make_client() as http:
        for item_id, rel, dst in todo:
            try:
                await _move_one(http, url, auth, source, library_fs, rel, dst)
            except CloudMoveError as exc:
                first = _record(session, item_id, rel, dst, str(exc))
                result.failed.append((Path(rel).name, str(exc), first))
                continue
            _record(session, item_id, rel, dst, "")
            result.moved += 1
        if result.moved:
            try:
                await _call(http, url, auth, "vfs/refresh", {"recursive": "true"})
            except CloudMoveError as exc:
                log.warning("refresh after move failed: %s", exc)
    return result
