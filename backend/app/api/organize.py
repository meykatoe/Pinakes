import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from app.api.match import ai_client, tmdb_client
from app.db import get_session
from app.models import Category, MediaItem
from app.services import matcher, organizer, scraper
from app.services.ai import AiClient
from app.services.tmdb import TmdbClient, TmdbError

router = APIRouter(prefix="/organize")


class ItemOut(BaseModel):
    id: int
    source_path: str
    status: str
    media_type: str
    tmdb_id: int | None
    title: str
    year: int | None
    season: int | None
    episode: int | None
    category_id: int | None
    target_path: str
    mode: str
    method: str | None
    reason: str
    error: str
    candidates: list[dict]
    companions: list[dict]


class ScanOut(BaseModel):
    created: int
    planned: int
    pending_review: int


class ChooseIn(BaseModel):
    tmdb_id: int | None = None
    category_id: int | None = None
    # 修正類型
    media_type: Literal["movie", "tv"] | None = None


class ProgressOut(BaseModel):
    running: bool
    done: int
    total: int
    current: str


class BatchOut(BaseModel):
    done: int
    skipped: int
    failed: int


def _out(session: Session, item: MediaItem, fresh: bool = True) -> ItemOut:
    if fresh:
        session.refresh(item)
    data = item.model_dump()
    data["candidates"] = json.loads(item.candidates)
    data["companions"] = json.loads(item.companions)
    return ItemOut(**data)


def _get(session: Session, item_id: int) -> MediaItem:
    item = session.get(MediaItem, item_id)
    if item is None:
        raise HTTPException(404, "項目不存在")
    return item


def _roots(session: Session) -> tuple[Path, Path]:
    try:
        return organizer.get_roots(session)
    except organizer.OrganizeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/items")
def list_items(
    status: str | None = None,
    q: str = "",
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> list[ItemOut]:
    stmt = select(MediaItem).order_by(MediaItem.updated_at.desc(), MediaItem.id.desc())
    if status:
        stmt = stmt.where(MediaItem.status == status)
    if needle := q.strip():
        like = f"%{needle}%"
        stmt = stmt.where(
            col(MediaItem.source_path).ilike(like) | col(MediaItem.title).ilike(like)
        )
    return [_out(session, i, False) for i in session.exec(stmt.limit(limit))]


@router.get("/summary")
def summary(session: Session = Depends(get_session)) -> dict[str, int]:
    stmt = select(MediaItem.status, func.count()).group_by(MediaItem.status)
    return {status: count for status, count in session.exec(stmt)}


@router.get("/scan/progress")
def scan_progress() -> ProgressOut:
    p = organizer.progress
    return ProgressOut(running=p.running, done=p.done, total=p.total, current=p.current)


@router.post("/scan")
async def scan(
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
    ai: AiClient | None = Depends(ai_client),
) -> ScanOut:
    inbox, library = _roots(session)
    if organizer.scan_lock.locked():
        raise HTTPException(409, "正在掃描中，請稍候")
    async with organizer.scan_lock:
        paths = organizer.new_paths(session, inbox)
        try:
            items = await organizer.plan_paths(
                session, client, ai, inbox, library, paths, track=True
            )
        except TmdbError as exc:
            raise HTTPException(502, str(exc)) from exc
    return ScanOut(
        created=len(items),
        planned=sum(i.status == "planned" for i in items),
        pending_review=sum(i.status == "pending_review" for i in items),
    )


@router.post("/items/{item_id}/choose")
async def choose(
    item_id: int,
    body: ChooseIn,
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
) -> ItemOut:
    item = _get(session, item_id)
    if item.status not in ("pending_review", "planned", "failed", "undone", "skipped"):
        raise HTTPException(422, "此項目目前無法重新選擇")
    inbox, library = _roots(session)
    media_type = body.media_type or item.media_type
    if body.category_id is not None:
        cat = session.get(Category, body.category_id)
        if cat is None:
            raise HTTPException(422, "分類不存在")
        if cat.media_type != media_type:
            raise HTTPException(422, "分類類型與項目不符")
        item.category_id = body.category_id
    try:
        if body.tmdb_id is not None:
            detail = await client.details(media_type, body.tmdb_id)
            forced = matcher.to_candidate(media_type, detail)
            await organizer.plan_item(session, client, None, item, inbox, library, forced)
        elif item.tmdb_id is not None:
            forced = matcher.Candidate(
                tmdb_id=item.tmdb_id, media_type=item.media_type,
                title=item.title, original_title=item.title, year=item.year,
            )
            await organizer.plan_item(session, client, None, item, inbox, library, forced)
        else:
            session.add(item)
            session.commit()
    except TmdbError as exc:
        raise HTTPException(502, str(exc)) from exc
    except (organizer.OrganizeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return _out(session, item)


@router.post("/items/{item_id}/skip")
def skip(item_id: int, session: Session = Depends(get_session)) -> ItemOut:
    item = _get(session, item_id)
    if item.status == "done":
        raise HTTPException(422, "已完成的項目請使用還原")
    item.status = "skipped"
    session.add(item)
    session.commit()
    return _out(session, item)


@router.post("/items/{item_id}/execute")
def execute(
    item_id: int, background: BackgroundTasks, session: Session = Depends(get_session)
) -> ItemOut:
    item = _get(session, item_id)
    background.add_task(scraper.scrape_in_background)
    try:
        return _out(session, organizer.execute_item(session, item))
    except organizer.OrganizeError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/execute")
def execute_all(
    background: BackgroundTasks, session: Session = Depends(get_session)
) -> BatchOut:
    background.add_task(scraper.scrape_in_background)
    out = BatchOut(done=0, skipped=0, failed=0)
    stmt = select(MediaItem).where(MediaItem.status == "planned").order_by(MediaItem.id)
    for item in list(session.exec(stmt)):
        try:
            organizer.execute_item(session, item)
        except organizer.OrganizeError:
            item.status = "failed"
        out.done += item.status == "done"
        out.skipped += item.status == "skipped"
        out.failed += item.status == "failed"
    return out


@router.post("/items/{item_id}/undo")
def undo(item_id: int, session: Session = Depends(get_session)) -> ItemOut:
    item = _get(session, item_id)
    try:
        return _out(session, organizer.undo_item(session, item))
    except organizer.OrganizeError as exc:
        raise HTTPException(422, str(exc)) from exc
