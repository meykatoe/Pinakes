import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.db import get_engine
from app.models import MediaItem, MediaMeta
from app.services import clients, nfo_export
from app.services.tmdb import TmdbClient, TmdbError

IMAGE_BASE = "https://image.tmdb.org/t/p"
SIZES = {"poster": "w500", "backdrop": "w1280"}
IMAGE_PATH = re.compile(r"^/[\w.-]+\.(?:jpg|jpeg|png|webp)$", re.I)
MAX_IMAGE_BYTES = 15 * 1024 * 1024
CAST_LIMIT = 8
log = logging.getLogger("pinakes.scraper")


def image_file(media_type: str, tmdb_id: int, kind: str) -> Path:
    return settings.data_dir / "images" / media_type / str(tmdb_id) / f"{kind}.jpg"


async def download_image(
    client: TmdbClient, remote: str | None, kind: str, dest: Path
) -> bool:
    if not remote or not IMAGE_PATH.match(remote):
        return False
    url = f"{IMAGE_BASE}/{SIZES[kind]}{remote}"
    async with httpx.AsyncClient(transport=client.transport, timeout=30) as http:
        try:
            res = await http.get(url)
        except httpx.HTTPError:
            return False
    if res.status_code != 200 or not 0 < len(res.content) <= MAX_IMAGE_BYTES:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(res.content)
    tmp.replace(dest)
    return True


def _year(date: str | None) -> int | None:
    return int(date[:4]) if date and date[:4].isdigit() else None


def pick_trailer(videos: dict) -> str:
    results = [
        v for v in videos.get("results", [])
        if v.get("site") == "YouTube" and v.get("type") == "Trailer"
    ]
    results.sort(key=lambda v: not v.get("official", False))
    return results[0]["key"] if results else ""


def build_meta(media_type: str, data: dict) -> MediaMeta:
    tv = media_type == "tv"
    runtimes = data.get("episode_run_time") or []
    return MediaMeta(
        media_type=media_type,
        tmdb_id=data["id"],
        title=data.get("name" if tv else "title", ""),
        original_title=data.get("original_name" if tv else "original_title", ""),
        year=_year(data.get("first_air_date" if tv else "release_date")),
        overview=data.get("overview") or "",
        tagline=data.get("tagline") or "",
        genres=json.dumps([g["name"] for g in data.get("genres", [])], ensure_ascii=False),
        rating=round(float(data.get("vote_average") or 0), 1),
        runtime=runtimes[0] if tv and runtimes else data.get("runtime"),
        seasons=data.get("number_of_seasons") if tv else None,
        imdb_id=data.get("imdb_id")
        or (data.get("external_ids") or {}).get("imdb_id")
        or "",
        credits=json.dumps(
            [
                {"name": c.get("name", ""), "character": c.get("character", "")}
                for c in data.get("credits", {}).get("cast", [])[:CAST_LIMIT]
            ],
            ensure_ascii=False,
        ),
        trailer_key=pick_trailer(data.get("videos", {})),
        poster_path=data.get("poster_path"),
        backdrop_path=data.get("backdrop_path"),
        scraped_at=datetime.now(UTC),
    )


async def scrape_one(
    session: Session, client: TmdbClient, media_type: str, tmdb_id: int
) -> MediaMeta:
    data = await client.details_full(media_type, tmdb_id)
    meta = build_meta(media_type, data)
    for kind, remote in (("poster", meta.poster_path), ("backdrop", meta.backdrop_path)):
        await download_image(client, remote, kind, image_file(media_type, tmdb_id, kind))
    session.merge(meta)
    session.commit()
    await nfo_export.export_media(session, client, media_type, tmdb_id)
    return meta


def _needs_scrape(session: Session, media_type: str, tmdb_id: int) -> bool:
    meta = session.get(MediaMeta, (media_type, tmdb_id))
    if meta is None:
        return True
    for kind, remote in (("poster", meta.poster_path), ("backdrop", meta.backdrop_path)):
        if remote and not image_file(media_type, tmdb_id, kind).exists():
            return True
    return False


async def scrape_missing(session: Session, client: TmdbClient) -> int:
    stmt = select(MediaItem.media_type, MediaItem.tmdb_id).where(
        MediaItem.status == "done", MediaItem.tmdb_id != None  # noqa: E711
    ).distinct()
    pairs = [(t, i) for t, i in session.exec(stmt) if _needs_scrape(session, t, i)]
    count = 0
    for media_type, tmdb_id in pairs:
        try:
            await scrape_one(session, client, media_type, tmdb_id)
        except TmdbError:
            break
        count += 1
    await nfo_export.export_all(session, client)
    return count


async def scrape_in_background() -> None:
    try:
        with Session(get_engine()) as session:
            await scrape_missing(session, clients.build_tmdb(session))
    except Exception:  # noqa: BLE001
        log.exception("background scrape failed")
