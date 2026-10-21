import asyncio
import json

import httpx
import pytest
from sqlmodel import Session, select

from app import db
from app.models import CloudMove
from app.services import cloud_move
from tests.test_rclone_sync import cycle, env  # noqa: F401
from tests.test_watcher import MATRIX, old_file

SUB = MATRIX.rsplit(".", 1)[0] + ".srt"

SRC = "pikpak:/downloads"
LIB = "pikpak:/Media"


class FakeRc:
    """以字典模擬雲端檔案。"""

    def __init__(self, files: set[str]):
        self.files = files
        self.calls: list[str] = []
        self.fail_move = ""

    def handler(self, request: httpx.Request) -> httpx.Response:
        action = request.url.path.lstrip("/")
        body = json.loads(request.content)
        self.calls.append(action)
        if action == "operations/stat":
            key = f"{body['fs']}/{body['remote']}"
            return httpx.Response(200, json={"item": {"Path": key} if key in self.files else None})
        if action == "operations/movefile":
            if self.fail_move:
                return httpx.Response(500, json={"error": self.fail_move})
            old = f"{body['srcFs']}/{body['srcRemote']}"
            self.files.remove(old)
            self.files.add(f"{body['dstFs']}/{body['dstRemote']}")
            return httpx.Response(200, json={})
        return httpx.Response(200, json={})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def configure(client, enabled=True):
    res = client.put("/api/settings", json={
        "sync_rc_url": "http://rc.local", "cloud_source_fs": SRC,
        "cloud_library_fs": LIB, "cloud_move_enabled": enabled,
    })
    assert res.status_code == 200


def run(rc: FakeRc):
    async def go():
        with Session(db.get_engine()) as s:
            return await cloud_move.process(s, rc.client())

    return asyncio.run(go())


@pytest.fixture
def organized(client, env):  # noqa: F811
    inbox, lib, src, make_tmdb = env
    old_file(src / "電影" / MATRIX)
    old_file(src / "電影" / SUB, b"sub")
    cycle(make_tmdb)
    return lib


def cloud_files():
    return {f"{SRC}/電影/{MATRIX}", f"{SRC}/電影/{SUB}"}


def test_moves_video_and_subtitle(client, organized):
    configure(client)
    rc = FakeRc(cloud_files())
    assert run(rc).failed == []
    assert len(rc.files) == 2 and all(f.startswith(LIB + "/") for f in rc.files)
    assert any(f.endswith(".mkv") for f in rc.files)
    assert any(f.endswith(".srt") for f in rc.files)
    with Session(db.get_engine()) as s:
        assert {m.status for m in s.exec(select(CloudMove))} == {"done"}


def test_not_repeated(client, organized):
    configure(client)
    rc = FakeRc(cloud_files())
    run(rc)
    rc.calls.clear()
    assert run(rc).failed == [] and rc.calls == []


def test_disabled_does_nothing(client, organized):
    configure(client, enabled=False)
    rc = FakeRc(cloud_files())
    assert run(rc).failed == [] and rc.calls == []
    assert rc.files == cloud_files()


def test_existing_target_not_overwritten(client, organized):
    configure(client)
    rc = FakeRc(cloud_files())
    run(FakeRc(set(rc.files)))
    with Session(db.get_engine()) as s:
        target = s.exec(select(CloudMove)).first().dst
    blocked = FakeRc(cloud_files() | {f"{LIB}/{target}"})
    with Session(db.get_engine()) as s:
        for row in s.exec(select(CloudMove)):
            s.delete(row)
        s.commit()
    failed = run(blocked).failed
    assert failed and "已存在" in failed[0][1] and failed[0][2] is True
    assert "operations/movefile" not in blocked.calls[:1]


def test_failure_recorded_and_limited(client, organized):
    configure(client)
    rc = FakeRc(cloud_files())
    rc.fail_move = "object not found"
    for _ in range(cloud_move.MAX_TRIES + 2):
        run(rc)
    with Session(db.get_engine()) as s:
        rows = list(s.exec(select(CloudMove)))
    assert rows and all(r.status == "failed" and r.tries == cloud_move.MAX_TRIES for r in rows)
    assert "object not found" in rows[0].error


def test_overlap_rejected(client):
    res = client.put("/api/settings", json={
        "cloud_source_fs": "pikpak:/downloads", "cloud_library_fs": "pikpak:/downloads/Media",
    })
    assert res.status_code == 422


def test_bad_fs_format_rejected(client):
    assert client.put("/api/settings", json={"cloud_library_fs": "no-colon"}).status_code == 422


def test_overlaps_helper():
    assert cloud_move.overlaps("a:", "a:/x")
    assert cloud_move.overlaps("a:/x", "a:/x/y")
    assert not cloud_move.overlaps("a:/x", "a:/xy")
    assert not cloud_move.overlaps("a:/x", "b:/x")


def test_rc_password_masked(client):
    client.put("/api/settings", json={"sync_rc_user": "u", "sync_rc_pass": "secret1234"})
    assert client.get("/api/settings").json()["sync_rc_pass"] == "****1234"


def sync_once():
    from app.services import rclone_sync

    async def go():
        with Session(db.get_engine()) as s:
            await rclone_sync.sync_once(s)

    asyncio.run(go())


def test_sync_once_moves_cloud_files(client, organized, monkeypatch):
    from app.services import rclone_sync

    configure(client)
    rc = FakeRc(cloud_files())
    monkeypatch.setattr(rclone_sync, "make_client", rc.client)
    sync_once()
    assert all(f.startswith(LIB + "/") for f in rc.files)
    data = client.get("/api/sync/status").json()
    assert data["last_cloud_moved"] == 2 and data["last_cloud_failed"] == 0


def test_cloud_failure_notified_once(client, organized, monkeypatch):
    from app.services import rclone_sync, watcher

    configure(client)
    rc = FakeRc(cloud_files())
    rc.fail_move = "boom"
    sent = []

    async def fake_digest(session, results):
        sent.append(results)

    monkeypatch.setattr(rclone_sync, "make_client", rc.client)
    monkeypatch.setattr(watcher, "send_digest", fake_digest)
    sync_once()
    sync_once()
    cloud = [r for batch in sent for r in batch if "雲端整理失敗" in r["error"]]
    assert len(cloud) == 2 and "boom" in cloud[0]["error"]
    assert client.get("/api/sync/status").json()["last_cloud_failed"] == 2


def test_bad_config_reported_not_raised(client, organized):
    from app.services import rclone_sync

    client.put("/api/settings", json={"cloud_move_enabled": True})
    sync_once()
    assert "遠端控制網址" in rclone_sync.status.last_error
