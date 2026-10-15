import httpx
import pytest

from app import db
from app.api.match import tmdb_client
from app.main import app
from app.services import matcher
from app.services.parser import ParsedMedia
from app.services.tmdb import TmdbClient, TmdbError
from sqlmodel import Session

MOVIES = {
    "The Matrix": [
        {"id": 603, "title": "駭客任務", "original_title": "The Matrix",
         "release_date": "1999-03-30", "popularity": 80},
        {"id": 604, "title": "駭客任務：重裝上陣",
         "original_title": "The Matrix Reloaded",
         "release_date": "2003-05-15", "popularity": 60},
    ],
    "Dune": [
        {"id": 1, "title": "沙丘", "original_title": "Dune",
         "release_date": "1984-12-14", "popularity": 20},
        {"id": 2, "title": "沙丘", "original_title": "Dune",
         "release_date": "2021-09-15", "popularity": 90},
    ],
}
TV = [{"id": 1396, "name": "絕命毒師", "original_name": "Breaking Bad",
       "first_air_date": "2008-01-20", "popularity": 100}]


class Fake:
    def __init__(self):
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        path, q = request.url.path, request.url.params
        if path == "/3/search/movie":
            items = MOVIES.get(q["query"], [])
            if q.get("year"):
                items = [i for i in items if i["release_date"][:4] == q["year"]]
            return httpx.Response(200, json={"results": items})
        if path == "/3/search/tv":
            items = TV if q["query"] == "Breaking Bad" else []
            return httpx.Response(200, json={"results": items})
        if path == "/3/tv/1396/season/2/episode/5":
            return httpx.Response(200, json={"name": "Breakage"})
        if path.startswith("/3/movie/"):
            wanted = int(path.rsplit("/", 1)[1])
            for items in MOVIES.values():
                for item in items:
                    if item["id"] == wanted:
                        return httpx.Response(200, json=item)
        return httpx.Response(404)


@pytest.fixture
def fake(client):
    fake = Fake()

    def make():
        with Session(db.get_engine()) as s:
            return TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(fake.handler))

    app.dependency_overrides[tmdb_client] = make
    yield fake
    app.dependency_overrides.pop(tmdb_client, None)


def test_confident_movie(client, fake):
    res = client.post(
        "/api/match/preview", json={"path": "The.Matrix.1999.1080p.BluRay.x264.mkv"}
    ).json()
    assert res["confident"] is True
    assert res["chosen"]["tmdb_id"] == 603
    assert res["target"] == "駭客任務 (1999)/駭客任務 (1999).mkv"


def test_ambiguous_needs_review(client, fake):
    res = client.post("/api/match/preview", json={"path": "Dune.1080p.mkv"}).json()
    assert res["confident"] is False
    assert res["chosen"] is None and res["target"] is None
    assert len(res["candidates"]) == 2


def test_year_disambiguates(client, fake):
    res = client.post("/api/match/preview", json={"path": "Dune.2021.1080p.mkv"}).json()
    assert res["confident"] is True
    assert res["chosen"]["tmdb_id"] == 2


def test_year_fallback_without_year(client, fake):
    res = client.post("/api/match/preview", json={"path": "The.Matrix.2000.mkv"}).json()
    assert len(res["candidates"]) == 2


def test_tv_with_episode_title(client, fake):
    res = client.post(
        "/api/match/preview", json={"path": "Breaking.Bad.S02E05.720p.mkv"}
    ).json()
    assert res["chosen"]["tmdb_id"] == 1396
    assert res["target"] == "絕命毒師 (2008)/Season 02/絕命毒師 - S02E05.mkv"


def test_forced_choice(client, fake):
    res = client.post(
        "/api/match/preview", json={"path": "whatever.mkv", "tmdb_id": 603}
    ).json()
    assert res["chosen"]["tmdb_id"] == 603
    assert res["target"].endswith(".mkv")


def test_no_result(client, fake):
    res = client.post("/api/match/preview", json={"path": "Unknown.Film.mkv"}).json()
    assert res["candidates"] == [] and res["chosen"] is None


def test_cache_avoids_second_call(client, fake):
    body = {"path": "The.Matrix.1999.mkv"}
    client.post("/api/match/preview", json=body)
    first = len(fake.calls)
    client.post("/api/match/preview", json=body)
    assert len(fake.calls) == first


def test_missing_key_returns_400(client):
    res = client.post("/api/match/preview", json={"path": "a.mkv"})
    assert res.status_code == 400


def test_tmdb_error_returns_502(client, fake):
    fake.handler = lambda req: httpx.Response(500)
    res = client.post("/api/match/preview", json={"path": "The.Matrix.1999.mkv"})
    assert res.status_code == 502


def test_score_title_and_year():
    cand = matcher.to_candidate("movie", MOVIES["The Matrix"][0])
    exact = matcher.score(ParsedMedia(title="The Matrix", year=1999), cand)
    wrong = matcher.score(ParsedMedia(title="The Matrix", year=2010), cand)
    assert exact == 1.0 and wrong < 0.9


def test_missing_key_raises():
    with pytest.raises(TmdbError):
        TmdbClient("")
