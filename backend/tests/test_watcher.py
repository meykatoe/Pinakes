import asyncio
import os
import time

import httpx
import pytest
from sqlmodel import Session

from app import db
from app.services import watcher
from app.services.tmdb import TmdbClient
from app.services.watcher import StabilityTracker
from tests.test_match import Fake

MATRIX = "The.Matrix.1999.1080p.BluRay.x264.mkv"


def old_file(path, data=b"video", age=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    t = time.time() - age
    os.utime(path, (t, t))
    return path


def test_tracker_requires_unchanged_window(tmp_path):
    f = old_file(tmp_path / "a.mkv")
    tr = StabilityTracker()
    t0 = time.time()
    assert tr.update([f], t0, 60) == []
    assert tr.update([f], t0 + 30, 60) == []
    assert tr.update([f], t0 + 61, 60) == [f]


def test_tracker_resets_when_file_grows(tmp_path):
    f = old_file(tmp_path / "a.mkv")
    tr = StabilityTracker()
    t0 = time.time()
    tr.update([f], t0, 60)
    f.write_bytes(b"video-more")
    os.utime(f, (t0 - 1000, t0 - 1000))
    assert tr.update([f], t0 + 61, 60) == []
    assert tr.update([f], t0 + 122, 60) == [f]


def test_tracker_recent_mtime_not_stable(tmp_path):
    f = tmp_path / "a.mkv"
    f.write_bytes(b"x")
    tr = StabilityTracker()
    t0 = time.time()
    os.utime(f, (t0 + 30, t0 + 30))
    tr.update([f], t0, 60)
    assert tr.update([f], t0 + 61, 60) == []


def test_tracker_zero_window(tmp_path):
    f = old_file(tmp_path / "a.mkv")
    assert StabilityTracker().update([f], time.time(), 0) == [f]


@pytest.fixture
def env(client, tmp_path):
    inbox, lib = tmp_path / "inbox", tmp_path / "lib"
    inbox.mkdir()
    lib.mkdir()
    client.put(
        "/api/library/paths", json={"inbox_path": str(inbox), "library_path": str(lib)}
    )
    client.put("/api/settings", json={"stable_seconds": 60})
    tm = Fake()

    def make_tmdb(session):
        return TmdbClient("k" * 32, "zh-TW", session, httpx.MockTransport(tm.handler))

    return inbox, lib, make_tmdb


def cycle(tracker, make_tmdb, now):
    async def go():
        with Session(db.get_engine()) as s:
            return await watcher.run_cycle(s, tracker, now, make_tmdb, lambda s: None)

    return asyncio.run(go())


def test_cycle_waits_then_organizes(client, env):
    inbox, lib, make_tmdb = env
    old_file(inbox / MATRIX)
    tr = StabilityTracker()
    t0 = time.time()
    assert cycle(tr, make_tmdb, t0) == []
    assert watcher.status.waiting == 1
    done = cycle(tr, make_tmdb, t0 + 61)
    assert [d["status"] for d in done] == ["done"]
    assert (lib / "電影/駭客任務 (1999)/駭客任務 (1999).mkv").exists()
    assert cycle(tr, make_tmdb, t0 + 122) == []


def test_cycle_without_auto_execute_only_plans(client, env):
    inbox, lib, make_tmdb = env
    client.put("/api/settings", json={"auto_execute": False})
    old_file(inbox / MATRIX)
    tr = StabilityTracker()
    t0 = time.time()
    cycle(tr, make_tmdb, t0)
    done = cycle(tr, make_tmdb, t0 + 61)
    assert [d["status"] for d in done] == ["planned"]
    assert not (lib / "電影").exists()


def test_cycle_ambiguous_goes_to_review(client, env):
    inbox, _, make_tmdb = env
    old_file(inbox / "Dune.1080p.mkv")
    tr = StabilityTracker()
    t0 = time.time()
    cycle(tr, make_tmdb, t0)
    done = cycle(tr, make_tmdb, t0 + 61)
    assert [d["status"] for d in done] == ["pending_review"]


def test_watch_settings_and_status(client):
    data = client.get("/api/settings").json()
    assert data["watch_enabled"] is False and data["auto_execute"] is True
    assert client.put("/api/settings", json={"watch_interval": 1}).status_code == 422
    client.put("/api/settings", json={"watch_enabled": True, "watch_interval": 10})
    st = client.get("/api/watch/status").json()
    assert st["enabled"] is True and st["running"] is False


def test_loop_starts_and_stops_cleanly(client):
    async def go():
        async with watcher.background():
            await asyncio.sleep(0.05)
            assert watcher.status.running is True
        assert watcher.status.running is False

    asyncio.run(go())
