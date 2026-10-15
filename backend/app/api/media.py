import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.match import tmdb_client
from app.db import get_session
from app.models import MediaItem, MediaMeta
from app.services import organizer, scraper
from app.services.tmdb import TmdbClient, TmdbError

router = APIRouter()

MediaType = Literal["movie", "tv"]


class Entry(BaseModel):
    media_type: str
    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    overview: str
    rating: float
    genres: list[str]
    poster_url: str | None
    backdrop_url: str | None
    category_id: int | None
    file_count: int
    added_at: str


class FileOut(BaseModel):
    item_id: int
    season: int | None
    episode: int | None
    target_path: str


class Detail(Entry):
    tagline: str
    runtime: int | None
    seasons: int | None
    credits: list[dict]
    trailer_key: str
    files: list[FileOut]


def _url(media_type: str, tmdb_id: int, kind: str) -> str | None:
    if scraper.image_file(media_type, tmdb_id, kind).exists():
        return f"/api/images/{media_type}/{tmdb_id}/{kind}"
    return None


def _entry(session: Session, items: list[MediaItem]) -> dict:
    latest = max(items, key=lambda i: i.updated_at)
    media_type, tmdb_id = latest.media_type, latest.tmdb_id
    meta = session.get(MediaMeta, (media_type, tmdb_id))
    return {
        "media_type": media_type,
        "tmdb_id": tmdb_id,
        "title": (meta.title if meta and meta.title else latest.title),
        "original_title": meta.original_title if meta else "",
        "year": meta.year if meta and meta.year else latest.year,
        "overview": meta.overview if meta else "",
        "rating": meta.rating if meta else 0.0,
        "genres": json.loads(meta.genres) if meta else [],
        "poster_url": _url(media_type, tmdb_id, "poster"),
        "backdrop_url": _url(media_type, tmdb_id, "backdrop"),
        "category_id": latest.category_id,
        "file_count": len(items),
        "added_at": latest.updated_at.isoformat(),
    }


def _grouped(session: Session) -> dict[tuple[str, int], list[MediaItem]]:
    stmt = select(MediaItem).where(
        MediaItem.status == "done", MediaItem.tmdb_id != None  # noqa: E711
    )
    groups: dict[tuple[str, int], list[MediaItem]] = {}
    for item in session.exec(stmt):
        groups.setdefault((item.media_type, item.tmdb_id), []).append(item)
    return groups


@router.get("/library/media")
def list_media(
    q: str = "",
    category_id: int | None = None,
    sort: Literal["recent", "title", "rating", "year"] = "recent",
    session: Session = Depends(get_session),
) -> list[Entry]:
    entries = [_entry(session, items) for items in _grouped(session).values()]
    if category_id is not None:
        entries = [e for e in entries if e["category_id"] == category_id]
    needle = q.strip().casefold()
    if needle:
        entries = [
            e for e in entries
            if needle in e["title"].casefold() or needle in e["original_title"].casefold()
        ]
    keys = {
        "recent": (lambda e: e["added_at"], True),
        "title": (lambda e: e["title"].casefold(), False),
        "rating": (lambda e: e["rating"], True),
        "year": (lambda e: e["year"] or 0, True),
    }
    key, reverse = keys[sort]
    entries.sort(key=key, reverse=reverse)
    return [Entry(**e) for e in entries]


@router.get("/library/media/{media_type}/{tmdb_id}")
def media_detail(
    media_type: MediaType, tmdb_id: int, session: Session = Depends(get_session)
) -> Detail:
    items = _grouped(session).get((media_type, tmdb_id))
    if not items:
        raise HTTPException(404, "找不到這部作品")
    meta = session.get(MediaMeta, (media_type, tmdb_id))
    files = sorted(items, key=lambda i: (i.season or 0, i.episode or 0, i.id))
    return Detail(
        **_entry(session, items),
        tagline=meta.tagline if meta else "",
        runtime=meta.runtime if meta else None,
        seasons=meta.seasons if meta else None,
        credits=json.loads(meta.credits) if meta else [],
        trailer_key=meta.trailer_key if meta else "",
        files=[
            FileOut(
                item_id=i.id, season=i.season, episode=i.episode,
                target_path=i.target_path,
            )
            for i in files
        ],
    )


@router.post("/library/scrape")
async def scrape_all(
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
) -> dict[str, int]:
    return {"scraped": await scraper.scrape_missing(session, client)}


@router.post("/library/media/{media_type}/{tmdb_id}/refresh")
async def refresh(
    media_type: MediaType,
    tmdb_id: int,
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
) -> dict[str, bool]:
    if (media_type, tmdb_id) not in _grouped(session):
        raise HTTPException(404, "找不到這部作品")
    try:
        await scraper.scrape_one(session, client, media_type, tmdb_id)
    except TmdbError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True}


@router.get("/images/{media_type}/{tmdb_id}/{kind}")
def image(media_type: MediaType, tmdb_id: int, kind: Literal["poster", "backdrop"]):
    path = scraper.image_file(media_type, tmdb_id, kind)
    if not path.is_file():
        raise HTTPException(404, "圖片不存在")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"}
    )


@router.delete("/library/media/{media_type}/{tmdb_id}")
def remove_media(
    media_type: MediaType, tmdb_id: int, session: Session = Depends(get_session)
) -> dict[str, int]:
    items = _grouped(session).get((media_type, tmdb_id))
    if not items:
        raise HTTPException(404, "找不到這部作品")
    removed, failed = 0, 0
    for item in items:
        try:
            organizer.undo_item(session, item)
            removed += 1
        except organizer.OrganizeError:
            failed += 1
    return {"removed": removed, "failed": failed}
