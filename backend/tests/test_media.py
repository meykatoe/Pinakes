import asyncio
import json

import httpx
import pytest
from sqlmodel import Session

from app import db
from app.api.match import tmdb_client
from app.main import app
from app.models import MediaItem
from app.services import scraper
from app.services.tmdb import TmdbClient
from tests.test_match import MOVIES

MOVIE = {
    **MOVIES["The Matrix"][0],
    "overview": "電腦世界的真相",
    "tagline": "歡迎來到真實世界",
    "genres": [{"name": "科幻"}, {"name": "動作"}],
    "vote_average": 8.2345,
    "runtime": 136,
    "poster_path": "/poster.jpg",
    "backdrop_path": "/back.jpg",
    "credits": {"cast": [{"name": f"演員{i}", "character": f"角色{i}"} for i in range(12)]},
    "videos": {
        "results": [
            {"site": "YouTube", "type": "Teaser", "key": "teaser", "official": True},
            {"site": "YouTube", "type": "Trailer", "key": "unofficial", "official": False},
            {"site": "YouTube", "type": "Trailer", "key": "official", "official": True},
        ]
    },
}
TV = {
    "id": 1396, "name": "絕命毒師", "original_name": "Breaking Bad",
    "first_air_date": "2008-01-20", "overview": "化學老師", "genres": [],
    "vote_average": 8.9, "episode_run_time": [47], "number_of_seasons": 5,
    "poster_path": None, "backdrop_path": None,
}


class Remote:
    def __init__(self):
        self.calls = []
        self.images_ok = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.url.host == "image.tmdb.org":
            if not self.images_ok:
                return httpx.Response(404)
            return httpx.Response(200, content=b"\xff\xd8fake-jpeg")
        if request.url.path == "/3/movie/603":
            return httpx.Response(200, json=MOVIE)
        if request.url.path == "/3/tv/1396":
            return httpx.Response(200, json=TV)
        return httpx.Response(404)


@pytest.fixture
def remote(client):
    r = Remote()

    def make():
        with Session(db.get_engine()) as s:
            return TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(r.handler))

    app.dependency_overrides[tmdb_client] = make
    yield r
    app.dependency_overrides.pop(tmdb_client, None)


def add_item(media_type="movie", tmdb_id=603, title="駭客任務", **kw):
    with Session(db.get_engine()) as s:
        item = MediaItem(
            source_path=f"/in/{tmdb_id}-{kw.get('episode', 0)}.mkv",
            status="done", media_type=media_type, tmdb_id=tmdb_id, title=title,
            year=1999, category_id=1,
            target_path=f"/lib/{title}.mkv", **kw,
        )
        s.add(item)
        s.commit()
        return item.id


def test_empty_wall(client):
    assert client.get("/api/library/media").json() == []


def test_scrape_and_list(client, remote):
    add_item()
    assert client.post("/api/library/scrape").json() == {"scraped": 1}
    entry = client.get("/api/library/media").json()[0]
    assert entry["rating"] == 8.2 and entry["genres"] == ["科幻", "動作"]
    assert entry["poster_url"] == "/api/images/movie/603/poster"
    img = client.get(entry["poster_url"])
    assert img.status_code == 200 and img.content.startswith(b"\xff\xd8")
    assert client.post("/api/library/scrape").json() == {"scraped": 0}


def test_detail_fields(client, remote):
    add_item()
    client.post("/api/library/scrape")
    d = client.get("/api/library/media/movie/603").json()
    assert d["trailer_key"] == "official"
    assert len(d["credits"]) == 8 and d["runtime"] == 136
    assert d["tagline"] == "歡迎來到真實世界"
    assert d["files"][0]["target_path"] == "/lib/駭客任務.mkv"


def test_tv_files_sorted(client, remote):
    add_item("tv", 1396, "絕命毒師", season=2, episode=5)
    add_item("tv", 1396, "絕命毒師", season=1, episode=2)
    add_item("tv", 1396, "絕命毒師", season=1, episode=1)
    client.post("/api/library/scrape")
    d = client.get("/api/library/media/tv/1396").json()
    assert [(f["season"], f["episode"]) for f in d["files"]] == [(1, 1), (1, 2), (2, 5)]
    assert d["seasons"] == 5 and d["runtime"] == 47 and d["file_count"] == 3
    assert len(client.get("/api/library/media").json()) == 1


def test_not_scraped_still_listed(client):
    add_item()
    entry = client.get("/api/library/media").json()[0]
    assert entry["title"] == "駭客任務" and entry["poster_url"] is None


def test_filters_and_sort(client, remote):
    add_item()
    add_item("tv", 1396, "絕命毒師", season=1, episode=1)
    client.post("/api/library/scrape")
    assert len(client.get("/api/library/media?q=matrix").json()) == 1
    assert len(client.get("/api/library/media?q=zzz").json()) == 0
    assert len(client.get("/api/library/media?category_id=99").json()) == 0
    by_rating = client.get("/api/library/media?sort=rating").json()
    assert by_rating[0]["tmdb_id"] == 1396
    assert client.get("/api/library/media?sort=bogus").status_code == 422


def test_image_failure_retries_later(client, remote):
    add_item()
    remote.images_ok = False
    assert client.post("/api/library/scrape").json() == {"scraped": 1}
    assert client.get("/api/library/media").json()[0]["poster_url"] is None
    remote.images_ok = True
    assert client.post("/api/library/scrape").json() == {"scraped": 1}
    assert client.get("/api/library/media").json()[0]["poster_url"] is not None


def test_refresh_and_404(client, remote):
    assert client.post("/api/library/media/movie/603/refresh").status_code == 404
    assert client.get("/api/library/media/movie/603").status_code == 404
    add_item()
    assert client.post("/api/library/media/movie/603/refresh").json() == {"ok": True}
    assert client.get("/api/library/media/movie/603").status_code == 200


def test_image_route_validation(client):
    assert client.get("/api/images/movie/1/poster").status_code == 404
    assert client.get("/api/images/..%2f/1/poster").status_code in (404, 422)
    assert client.get("/api/images/movie/1/other").status_code == 422


def test_bad_image_paths_not_downloaded(client, remote, tmp_path):
    async def go(path):
        with Session(db.get_engine()) as s:
            c = TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(remote.handler))
            return await scraper.download_image(c, path, "poster", tmp_path / "x.jpg")

    for bad in ["http://evil/x.jpg", "/../../x.jpg", "x.jpg", "/a b.jpg", None]:
        assert asyncio.run(go(bad)) is False
    assert remote.calls == []


def test_meta_builder_defaults():
    meta = scraper.build_meta("movie", {"id": 5, "title": "T"})
    assert meta.genres == "[]" and meta.trailer_key == "" and meta.year is None
    assert json.loads(meta.credits) == []


def test_item_refs(client):
    a = add_item("tv", 1396, "絕命毒師", season=2, episode=5)
    b = add_item()
    with Session(db.get_engine()) as s:
        gone = MediaItem(
            source_path="/in/x.mkv", status="undone", media_type="movie",
            tmdb_id=1, title="x", target_path="/lib/x.mkv",
        )
        s.add(gone)
        s.commit()
        gone_id = gone.id
    res = client.get(f"/api/library/items?ids={a}&ids={b}&ids={gone_id}&ids=9999").json()
    by_id = {r["item_id"]: r for r in res}
    assert set(by_id) == {a, b}
    assert by_id[a] == {
        "item_id": a, "media_type": "tv", "tmdb_id": 1396, "season": 2, "episode": 5,
    }
    assert by_id[b]["media_type"] == "movie" and by_id[b]["season"] is None


def test_item_refs_empty_and_limit(client):
    assert client.get("/api/library/items").json() == []
    many = "&".join(f"ids={n}" for n in range(101))
    assert client.get(f"/api/library/items?{many}").status_code == 422
    assert client.get("/api/library/items?ids=abc").status_code == 422
