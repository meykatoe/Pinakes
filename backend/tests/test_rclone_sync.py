import asyncio
import time

import httpx
import pytest
from sqlmodel import Session, func, select

from app import db
from app.models import SyncedFile
from app.services import rclone_sync, settings_store, watcher
from app.services.rclone_sync import SyncError
from app.services.tmdb import TmdbClient
from tests.test_match import Fake
from tests.test_watcher import MATRIX, old_file


@pytest.fixture
def env(client, tmp_path):
    inbox, lib, src = tmp_path / "inbox", tmp_path / "lib", tmp_path / "mount"
    for d in (inbox, lib, src):
        d.mkdir()
    client.put(
        "/api/library/paths", json={"inbox_path": str(inbox), "library_path": str(lib)}
    )
    client.put("/api/settings", json={
        "stable_seconds": 60, "sync_source_path": str(src),
        "sync_enabled": True,
    })
    tm = Fake()

    def make_tmdb(session):
        return TmdbClient("k" * 32, "zh-TW", session, httpx.MockTransport(tm.handler))

    rclone_sync.status.last_run = None
    return inbox, lib, src, make_tmdb


def cycle(make_tmdb, now=None):
    async def go():
        with Session(db.get_engine()) as s:
            return await rclone_sync.run_cycle(
                s, now or time.time(), make_tmdb, lambda s: None
            )

    return asyncio.run(go())


def synced_count():
    with Session(db.get_engine()) as s:
        return s.exec(select(func.count()).select_from(SyncedFile)).one()


def test_copy_and_organize(env):
    inbox, lib, src, make_tmdb = env
    old_file(src / "電影" / MATRIX)
    old_file(src / "電影" / "The.Matrix.1999.srt", b"sub")
    res = cycle(make_tmdb)
    assert [r["status"] for r in res] == ["done"]
    assert synced_count() == 2
    assert (src / "電影" / MATRIX).exists()
    assert not list(inbox.rglob("*.part")) and not list(inbox.rglob(".*.part"))
    assert any(p.suffix == ".mkv" for p in lib.rglob("*"))


def test_not_repeated_after_move(env):
    inbox, lib, src, make_tmdb = env
    old_file(src / MATRIX)
    with Session(db.get_engine()) as s:
        settings_store.set_value(s, "organize_mode", "move")
    assert len(cycle(make_tmdb)) == 1
    assert cycle(make_tmdb) == []
    assert not list(inbox.glob("*.mkv"))


def test_recent_file_skipped(env):
    inbox, lib, src, make_tmdb = env
    old_file(src / MATRIX, age=5)
    assert cycle(make_tmdb) == []
    assert synced_count() == 0
    assert len(cycle(make_tmdb, time.time() + 120)) == 1


def test_changed_file_synced_again(env):
    inbox, lib, src, make_tmdb = env
    old_file(src / MATRIX, b"v1")
    cycle(make_tmdb)
    old_file(src / MATRIX, b"version-two")
    res = cycle(make_tmdb)
    assert [r["status"] for r in res] == ["failed"]
    assert synced_count() == 1


def test_no_auto_organize(client, env):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_auto_organize": False})
    old_file(src / MATRIX)
    res = cycle(make_tmdb)
    assert [r["status"] for r in res] == ["synced"]
    assert (inbox / MATRIX).exists()
    assert not list(lib.rglob("*.mkv"))


def test_ignores_non_media_and_hidden(env):
    inbox, lib, src, make_tmdb = env
    old_file(src / "note.txt")
    old_file(src / ".trash" / MATRIX)
    assert cycle(make_tmdb) == []
    assert not any(inbox.iterdir())


def test_conflicting_dest_reported(client, env):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_auto_organize": False})
    old_file(src / MATRIX, b"remote-data")
    old_file(inbox / MATRIX, b"x")
    res = cycle(make_tmdb)
    assert res[0]["status"] == "failed"
    assert (inbox / MATRIX).read_bytes() == b"x"
    assert synced_count() == 0


def test_source_validation(client, env, tmp_path):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_source_path": str(tmp_path)})
    with pytest.raises(SyncError, match="不可包含"):
        cycle(make_tmdb)
    nested = inbox / "sub"
    nested.mkdir()
    client.put("/api/settings", json={"sync_source_path": str(nested)})
    with pytest.raises(SyncError, match="不可位於"):
        cycle(make_tmdb)
    res = client.put("/api/settings", json={"sync_source_path": "/no/such/dir"})
    assert res.status_code == 422


def test_rc_refresh_called_and_failure_nonfatal(client, env, monkeypatch):
    inbox, lib, src, make_tmdb = env
    calls = []
    state = {"status": 200}

    def handler(request):
        calls.append(request)
        return httpx.Response(state["status"])

    monkeypatch.setattr(
        rclone_sync, "make_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    client.put("/api/settings", json={"sync_rc_url": "http://127.0.0.1:5572/"})
    old_file(src / MATRIX)
    cycle(make_tmdb)
    assert str(calls[0].url) == "http://127.0.0.1:5572/vfs/refresh"
    assert rclone_sync.status.last_error == ""
    state["status"] = 500
    old_file(src / "B.2000.mkv")
    assert len(cycle(make_tmdb)) == 1
    assert "500" in rclone_sync.status.last_error


def test_due_schedule(client, env):
    with Session(db.get_engine()) as s:
        now = time.time()
        rclone_sync.status.last_run = None
        assert rclone_sync.due(s, now)
        rclone_sync.status.last_run = now - 60 * 10
        assert not rclone_sync.due(s, now)
        rclone_sync.status.last_run = now - 60 * 31
        assert rclone_sync.due(s, now)
    client.put("/api/settings", json={"sync_enabled": False})
    with Session(db.get_engine()) as s:
        assert not rclone_sync.due(s, now)


def test_sync_once_sends_digest(client, env, monkeypatch):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_auto_organize": False})
    old_file(src / MATRIX)
    sent = []

    async def fake_digest(session, results):
        sent.append(results)

    monkeypatch.setattr(watcher, "send_digest", fake_digest)

    async def go():
        with Session(db.get_engine()) as s:
            await rclone_sync.sync_once(s)

    asyncio.run(go())
    assert sent and sent[0][0]["status"] == "synced"
    assert rclone_sync.status.last_run is not None and not rclone_sync.status.busy


def test_status_api(client):
    data = client.get("/api/sync/status").json()
    assert data["enabled"] is False and data["busy"] is False


def test_failure_notified_once(client, env):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_auto_organize": False})
    old_file(src / MATRIX, b"remote-data")
    old_file(inbox / MATRIX, b"x")
    assert [r["status"] for r in cycle(make_tmdb)] == ["failed"]
    assert cycle(make_tmdb) == []
    assert rclone_sync.status.last_failed == 1
    old_file(src / MATRIX, b"remote-data-v2")
    assert [r["status"] for r in cycle(make_tmdb)] == ["failed"]
    (inbox / MATRIX).unlink()
    assert [r["status"] for r in cycle(make_tmdb)] == ["synced"]
    assert rclone_sync.status.last_failed == 0
    (inbox / MATRIX).unlink()
    old_file(inbox / MATRIX, b"y")
    old_file(src / MATRIX, b"remote-data-version-3")
    assert [r["status"] for r in cycle(make_tmdb)] == ["failed"]


def test_run_api_starts_and_finishes(client, env):
    inbox, lib, src, make_tmdb = env
    client.put("/api/settings", json={"sync_auto_organize": False})
    old_file(src / MATRIX)
    assert client.post("/api/sync/run").json() == {"started": True}
    for _ in range(100):
        data = client.get("/api/sync/status").json()
        if not data["busy"]:
            break
        time.sleep(0.05)
    assert not data["busy"] and data["last_run"] is not None
    assert (inbox / MATRIX).exists()
    assert client.post("/api/sync/run").json() == {"started": True}
