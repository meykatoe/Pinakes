import asyncio
import json
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app import db
from app.models import MediaMeta, OperationLog
from app.services import nfo_export, settings_store
from app.services.tmdb import TmdbClient
from tests.test_match import Fake
from tests.test_organize import MATRIX, env, make  # noqa: F401


def enable(images: bool = True) -> None:
    with Session(db.get_engine()) as s:
        settings_store.set_value(s, "nfo_enabled", "true")
        settings_store.set_value(s, "nfo_images", "true" if images else "false")


def add_meta(media_type: str, tmdb_id: int, title: str) -> None:
    with Session(db.get_engine()) as s:
        s.merge(MediaMeta(media_type=media_type, tmdb_id=tmdb_id, title=title,
                          genres=json.dumps(["Drama"])))
        s.commit()


def put_image(media_type: str, tmdb_id: int, kind: str) -> None:
    from app.services import scraper

    path = scraper.image_file(media_type, tmdb_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"img")


def run_export() -> Fake:
    fake = Fake()

    async def go():
        with Session(db.get_engine()) as s:
            client = TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(fake.handler))
            await nfo_export.export_all(s, client)

    asyncio.run(go())
    return fake


def nfo_logs() -> list[OperationLog]:
    with Session(db.get_engine()) as s:
        return list(s.exec(select(OperationLog).where(OperationLog.action == "nfo")))


def test_show_root():
    t = Path("/lib/tv/Show/Season 01/Show - S01E01.mkv")
    assert nfo_export.show_root(t, "{title}/Season {season:02}/{title}") == t.parents[1]
    flat = Path("/lib/tv/Show/Show S01E01.mkv")
    assert nfo_export.show_root(flat, "{title}/{title} S{season}E{episode}") == flat.parent


def test_disabled_by_default(client, env):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    add_meta("movie", 603, "Matrix")
    run_export()
    assert not list((lib / "電影").rglob("*.nfo"))


def test_movie_files_and_undo(client, env):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    add_meta("movie", 603, "Matrix")
    put_image("movie", 603, "poster")
    enable()
    run_export()
    folder = lib / "電影/駭客任務 (1999)"
    assert (folder / "movie.nfo").is_file()
    assert (folder / "poster.jpg").read_bytes() == b"img"
    assert not (folder / "fanart.jpg").exists()
    assert "<title>Matrix</title>" in (folder / "movie.nfo").read_text("utf-8")
    run_export()
    assert len(nfo_logs()) == 2

    item = client.get("/api/organize/items").json()[0]
    client.post(f"/api/organize/items/{item['id']}/undo")
    assert not (lib / "電影").exists()


def test_existing_nfo_not_overwritten(client, env):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    add_meta("movie", 603, "Matrix")
    folder = lib / "電影/駭客任務 (1999)"
    (folder / "movie.nfo").write_text("mine")
    enable(images=False)
    run_export()
    assert (folder / "movie.nfo").read_text() == "mine"
    assert nfo_logs() == []


def test_tv_show_file_shared_between_episodes(client, env):
    inbox, lib, _ = env
    make(inbox, "Breaking.Bad.S02E05.720p.mkv")
    make(inbox, "Breaking.Bad.S02E06.720p.mkv")
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    items = client.get("/api/organize/items").json()
    tmdb_id = items[0]["tmdb_id"]
    add_meta("tv", tmdb_id, "Breaking Bad")
    enable(images=False)
    root = lib / "影集/絕命毒師 (2008)"
    run_export()
    assert (root / "tvshow.nfo").is_file()
    ep5 = root / "Season 02/絕命毒師 - S02E05.nfo"
    assert "<title>Breakage</title>" in ep5.read_text("utf-8")
    assert not (root / "Season 02/絕命毒師 - S02E06.nfo").exists()
    assert len(nfo_logs()) == 2
    run_export()
    assert len(nfo_logs()) == 2

    client.post(f"/api/organize/items/{items[0]['id']}/undo")
    assert (root / "tvshow.nfo").is_file()
    client.post(f"/api/organize/items/{items[1]['id']}/undo")
    assert not (lib / "影集").exists()


def test_episode_fetch_stops_after_misses(client, env):
    inbox, lib, _ = env
    for ep in range(6, 12):
        make(inbox, f"Breaking.Bad.S02E{ep:02}.720p.mkv")
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    items = client.get("/api/organize/items").json()
    add_meta("tv", items[0]["tmdb_id"], "Breaking Bad")
    enable(images=False)
    fake = run_export()
    asked = [c for c in fake.calls if "/episode/" in c]
    assert len(asked) == nfo_export.MAX_MISSES
    assert (lib / "影集/絕命毒師 (2008)/tvshow.nfo").is_file()


def test_flat_movie_uses_stem_names(client, env):
    inbox, lib, _ = env
    with Session(db.get_engine()) as s:
        settings_store.set_value(s, "movie_template", "{title} ({year})")
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    add_meta("movie", 603, "Matrix")
    enable(images=False)
    run_export()
    assert (lib / "電影/駭客任務 (1999).nfo").is_file()
    assert not (lib / "電影/movie.nfo").exists()


def test_settings_roundtrip(client):
    body = client.get("/api/settings").json()
    assert body["nfo_enabled"] is False and body["nfo_images"] is True
    res = client.put("/api/settings", json={"nfo_enabled": True, "nfo_images": False})
    assert res.json()["nfo_enabled"] is True and res.json()["nfo_images"] is False


def test_rebuild_requires_enabled(client):
    assert client.post("/api/library/nfo").status_code == 400


def test_rebuild_refreshes_old_meta_and_writes(client, env, monkeypatch):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    client.post("/api/organize/execute")
    add_meta("movie", 603, "Matrix")
    enable(images=False)
    seen = []

    async def fake_scrape(session, tmdb, media_type, tmdb_id):
        seen.append((media_type, tmdb_id))
        meta = session.get(MediaMeta, (media_type, tmdb_id))
        meta.imdb_id = "tt0133093"
        session.add(meta)
        session.commit()

    from app.services import scraper

    monkeypatch.setattr(scraper, "scrape_one", fake_scrape)

    async def go():
        with Session(db.get_engine()) as s:
            tmdb = TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(Fake().handler))
            await scraper.rebuild_nfo(s, tmdb)

    asyncio.run(go())
    assert seen == [("movie", 603)]
    text = (lib / "電影/駭客任務 (1999)/movie.nfo").read_text("utf-8")
    assert "tt0133093" in text


def test_rebuild_endpoint_starts_once(client, monkeypatch):
    from app.services import scraper

    with Session(db.get_engine()) as s:
        settings_store.set_value(s, "nfo_enabled", "true")
    calls = []

    async def fake_bg():
        calls.append(1)

    monkeypatch.setattr(scraper, "rebuild_nfo_in_background", fake_bg)
    monkeypatch.setitem(scraper.rebuild_state, "running", False)
    assert client.post("/api/library/nfo").json() == {"started": True}
    assert calls == [1]
    scraper.rebuild_state["running"] = True
    assert client.post("/api/library/nfo").json() == {"started": False}
    scraper.rebuild_state["running"] = False
