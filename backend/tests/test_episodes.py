import httpx
import pytest
from sqlmodel import Session

from app import db
from app.api.match import tmdb_client
from app.main import app
from app.models import MediaItem
from app.services.tmdb import TmdbClient

SEASONS = {
    0: [{"episode_number": 1, "name": "特別篇", "air_date": "2008-01-01"}],
    1: [
        {"episode_number": 1, "name": "試播", "air_date": "2008-01-20"},
        {"episode_number": 2, "name": "貓在袋中", "air_date": "2008-01-27"},
        {"episode_number": 3, "name": "貓在袋裡", "air_date": "2008-02-10"},
        {"episode_number": 4, "name": "尚未播出", "air_date": "2999-01-01"},
        {"episode_number": 5, "name": "未排定", "air_date": None},
    ],
    2: [{"episode_number": 1, "name": "第二季開場", "air_date": "2009-03-08"}],
}


@pytest.fixture
def remote(client):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.startswith("/3/tv/1396/season/"):
            number = int(request.url.path.rsplit("/", 1)[-1])
            if number in SEASONS:
                return httpx.Response(200, json={"episodes": SEASONS[number]})
        return httpx.Response(404)

    def make():
        with Session(db.get_engine()) as s:
            return TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(handler))

    app.dependency_overrides[tmdb_client] = make
    yield calls
    app.dependency_overrides.pop(tmdb_client, None)


def add(season, episode, tmdb_id=1396, media_type="tv", status="done"):
    with Session(db.get_engine()) as s:
        s.add(
            MediaItem(
                source_path=f"/in/{media_type}-{tmdb_id}-{season}-{episode}.mkv",
                status=status, media_type=media_type, tmdb_id=tmdb_id,
                title="絕命毒師", season=season, episode=episode,
                target_path=f"/lib/{season}-{episode}.mkv",
            )
        )
        s.commit()


def test_reports_missing_aired_only(client, remote):
    add(1, 1)
    add(1, 3)
    res = client.get("/api/library/media/tv/1396/missing")
    assert res.status_code == 200
    assert res.json() == [
        {
            "season": 1, "aired": 3, "owned": 2,
            "missing": [{"episode": 2, "name": "貓在袋中", "air_date": "2008-01-27"}],
        }
    ]


def test_complete_season_has_no_gap(client, remote):
    for ep in (1, 2, 3):
        add(1, ep)
    gap = client.get("/api/library/media/tv/1396/missing").json()[0]
    assert gap["missing"] == [] and gap["aired"] == gap["owned"] == 3


def test_only_owned_seasons_checked(client, remote):
    add(2, 1)
    res = client.get("/api/library/media/tv/1396/missing").json()
    assert [g["season"] for g in res] == [2]
    assert remote == ["/3/tv/1396/season/2"]


def test_specials_skipped(client, remote):
    add(0, 1)
    add(1, 1)
    res = client.get("/api/library/media/tv/1396/missing").json()
    assert [g["season"] for g in res] == [1]


def test_files_without_episode_ignored(client, remote):
    with Session(db.get_engine()) as s:
        s.add(
            MediaItem(
                source_path="/in/x.mkv", status="done", media_type="tv",
                tmdb_id=1396, title="絕命毒師", target_path="/lib/x.mkv",
            )
        )
        s.commit()
    assert client.get("/api/library/media/tv/1396/missing").json() == []


def test_unknown_show_404(client, remote):
    assert client.get("/api/library/media/tv/1396/missing").status_code == 404


def test_undone_files_not_counted(client, remote):
    add(1, 1)
    add(1, 2, status="undone")
    gap = client.get("/api/library/media/tv/1396/missing").json()[0]
    assert gap["owned"] == 1
    assert [m["episode"] for m in gap["missing"]] == [2, 3]


def test_tmdb_failure_returns_502(client, remote):
    add(9, 1)
    assert client.get("/api/library/media/tv/1396/missing").status_code == 502
