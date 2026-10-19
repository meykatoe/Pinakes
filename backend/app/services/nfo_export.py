import shutil
from pathlib import Path

from sqlmodel import Session, select

from app.models import Category, MediaItem, MediaMeta, OperationLog
from app.services import fileops, nfo, organizer, settings_store
from app.services.tmdb import TmdbClient, TmdbError

MAX_MISSES = 3
IMAGE_KINDS = (("poster", "poster"), ("backdrop", "fanart"))


def show_root(target: Path, template: str) -> Path:
    parts = template.split("/")
    idx = next(
        (i for i, p in enumerate(parts) if "{season" in p or "{episode" in p),
        len(parts) - 1,
    )
    levels = len(parts) - idx
    if levels > len(target.parents):
        return target
    return target.parents[levels - 1]


def _write(session: Session, item: MediaItem, dst: Path, writer) -> bool:
    if fileops.exists(dst):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".pinakes-tmp")
    try:
        writer(tmp)
        tmp.replace(dst)
    except OSError:
        tmp.unlink(missing_ok=True)
        return False
    session.add(
        OperationLog(item_id=item.id, action="nfo", src="", dst=str(dst))
    )
    session.commit()
    return True


def _images(session: Session, item: MediaItem, meta: MediaMeta, names: dict) -> None:
    from app.services import scraper

    if settings_store.get_value(session, "nfo_images") != "true":
        return
    for kind, label in IMAGE_KINDS:
        src = scraper.image_file(meta.media_type, meta.tmdb_id, kind)
        if src.is_file():
            _write(session, item, names[label], lambda tmp, s=src: shutil.copyfile(s, tmp))


def _text(content: str):
    return lambda tmp: tmp.write_text(content, encoding="utf-8")


def _export_movie(session, item, meta, base: Path) -> None:
    target = Path(item.target_path)
    if target.parent != base:
        folder = target.parent
        names = {"nfo": folder / "movie.nfo", "poster": folder / "poster.jpg",
                 "fanart": folder / "fanart.jpg"}
    else:
        stem = target.with_suffix("")
        names = {"nfo": stem.with_suffix(".nfo"),
                 "poster": stem.with_name(stem.name + "-poster.jpg"),
                 "fanart": stem.with_name(stem.name + "-fanart.jpg")}
    _write(session, item, names["nfo"], _text(nfo.movie_nfo(meta)))
    _images(session, item, meta, names)


def _export_tv(session, item, meta, base: Path, ep: dict | None) -> None:
    if ep is not None:
        target = Path(item.target_path)
        _write(session, item, target.with_suffix(".nfo"), _text(nfo.episode_nfo(meta, ep)))
    template = settings_store.get_value(session, "tv_template")
    root = show_root(Path(item.target_path), template)
    if root == base or base not in root.parents:
        return
    names = {"poster": root / "poster.jpg", "fanart": root / "fanart.jpg"}
    _write(session, item, root / "tvshow.nfo", _text(nfo.tvshow_nfo(meta)))
    _images(session, item, meta, names)


def export_item(
    session: Session, item: MediaItem, meta: MediaMeta, library: Path,
    ep: dict | None = None,
) -> None:
    category = session.get(Category, item.category_id) if item.category_id else None
    if category is None:
        return
    base = library / category.subdir
    target = Path(item.target_path)
    try:
        fileops.ensure_within(target, library)
        if item.media_type == "tv":
            _export_tv(session, item, meta, base, ep)
        else:
            _export_movie(session, item, meta, base)
    except fileops.FileOpError:
        return


async def _fetch_episodes(client: TmdbClient, items: list[MediaItem]) -> dict[int, dict]:
    found, misses = {}, 0
    for item in items:
        if item.media_type != "tv" or item.season is None or item.episode is None:
            continue
        if fileops.exists(Path(item.target_path).with_suffix(".nfo")):
            continue
        try:
            found[item.id] = await client.episode(item.tmdb_id, item.season, item.episode)
        except TmdbError:
            misses += 1
            if misses >= MAX_MISSES:
                break
    return found


async def export_media(
    session: Session, client: TmdbClient, media_type: str, tmdb_id: int
) -> None:
    if settings_store.get_value(session, "nfo_enabled") != "true":
        return
    meta = session.get(MediaMeta, (media_type, tmdb_id))
    if meta is None:
        return
    try:
        _, library = organizer.get_roots(session)
    except organizer.OrganizeError:
        return
    stmt = select(MediaItem).where(
        MediaItem.status == "done",
        MediaItem.media_type == media_type,
        MediaItem.tmdb_id == tmdb_id,
    )
    items = [i for i in session.exec(stmt) if Path(i.target_path).is_file()]
    episodes = await _fetch_episodes(client, items)
    with organizer.execute_lock:
        for item in items:
            export_item(session, item, meta, library, episodes.get(item.id))


async def export_all(session: Session, client: TmdbClient) -> None:
    if settings_store.get_value(session, "nfo_enabled") != "true":
        return
    stmt = select(MediaItem.media_type, MediaItem.tmdb_id).where(
        MediaItem.status == "done", MediaItem.tmdb_id != None  # noqa: E711
    ).distinct()
    for media_type, tmdb_id in list(session.exec(stmt)):
        await export_media(session, client, media_type, tmdb_id)
