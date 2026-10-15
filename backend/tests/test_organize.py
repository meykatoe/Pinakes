import os
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session

from app import db
from app.api.match import ai_client, tmdb_client
from app.main import app
from app.services.fileops import FileOpError, ensure_within
from app.services.tmdb import TmdbClient
from tests.test_ai import FakeAi, make_ai
from tests.test_match import Fake


@pytest.fixture
def env(client, tmp_path):
    inbox, lib = tmp_path / "inbox", tmp_path / "lib"
    inbox.mkdir()
    lib.mkdir()
    res = client.put(
        "/api/library/paths", json={"inbox_path": str(inbox), "library_path": str(lib)}
    )
    assert res.status_code == 200
    tm = Fake()
    state = {"ai": None}

    def tmdb():
        with Session(db.get_engine()) as s:
            return TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(tm.handler))

    def ai():
        if state["ai"] is None:
            return None
        return make_ai(Session(db.get_engine()), state["ai"])

    app.dependency_overrides[tmdb_client] = tmdb
    app.dependency_overrides[ai_client] = ai
    yield inbox, lib, state
    app.dependency_overrides.pop(tmdb_client, None)
    app.dependency_overrides.pop(ai_client, None)


def make(inbox: Path, name: str, data: bytes = b"video") -> Path:
    path = inbox / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


MATRIX = "The.Matrix.1999.1080p.BluRay.x264.mkv"
TARGET = "電影/駭客任務 (1999)/駭客任務 (1999).mkv"


def test_scan_plan_execute_undo_hardlink(client, env):
    inbox, lib, _ = env
    src = make(inbox, MATRIX)
    res = client.post("/api/organize/scan").json()
    assert res == {"created": 1, "planned": 1, "pending_review": 0}
    item = client.get("/api/organize/items").json()[0]
    assert item["target_path"] == str(lib / TARGET)
    assert not (lib / TARGET).exists()

    done = client.post(f"/api/organize/items/{item['id']}/execute").json()
    assert done["status"] == "done"
    assert os.path.samefile(src, lib / TARGET)

    undone = client.post(f"/api/organize/items/{item['id']}/undo").json()
    assert undone["status"] == "undone"
    assert src.exists() and not (lib / "電影").exists()


def test_rescan_does_not_duplicate(client, env):
    inbox, _, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    again = client.post("/api/organize/scan").json()
    assert again["created"] == 0
    assert len(client.get("/api/organize/items").json()) == 1


def test_ambiguous_then_choose(client, env):
    inbox, lib, _ = env
    make(inbox, "Dune.1080p.mkv")
    res = client.post("/api/organize/scan").json()
    assert res["pending_review"] == 1
    item = client.get("/api/organize/items").json()[0]
    assert client.post(f"/api/organize/items/{item['id']}/execute").status_code == 422
    chosen = client.post(
        f"/api/organize/items/{item['id']}/choose", json={"tmdb_id": 2}
    ).json()
    assert chosen["status"] == "planned" and chosen["method"] == "manual"
    assert chosen["target_path"] == str(lib / "電影/沙丘 (2021)/沙丘 (2021).mkv")


def test_move_mode_and_undo(client, env):
    inbox, lib, _ = env
    client.put("/api/settings", json={"organize_mode": "move"})
    src = make(inbox, MATRIX)
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    client.post(f"/api/organize/items/{item['id']}/execute")
    assert not src.exists() and (lib / TARGET).exists()
    client.post(f"/api/organize/items/{item['id']}/undo")
    assert src.read_bytes() == b"video" and not (lib / TARGET).exists()


def test_subtitles_follow(client, env):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    make(inbox, "The.Matrix.1999.1080p.BluRay.x264.zh-TW.srt", b"sub")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    assert len(item["companions"]) == 1
    client.post(f"/api/organize/items/{item['id']}/execute")
    assert (lib / "電影/駭客任務 (1999)/駭客任務 (1999).zh-TW.srt").read_bytes() == b"sub"
    client.post(f"/api/organize/items/{item['id']}/undo")
    assert not (lib / "電影").exists()


def _existing(lib: Path, data: bytes):
    path = lib / TARGET
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    return path


def test_conflict_skip(client, env):
    inbox, lib, _ = env
    old = _existing(lib, b"old")
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    res = client.post(f"/api/organize/items/{item['id']}/execute").json()
    assert res["status"] == "skipped" and old.read_bytes() == b"old"


def test_conflict_overwrite_and_undo(client, env):
    inbox, lib, _ = env
    client.put("/api/settings", json={"conflict_policy": "overwrite"})
    old = _existing(lib, b"old")
    make(inbox, MATRIX, b"new-data")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    client.post(f"/api/organize/items/{item['id']}/execute")
    assert old.read_bytes() == b"new-data"
    client.post(f"/api/organize/items/{item['id']}/undo")
    assert old.read_bytes() == b"old"


def test_keep_larger(client, env):
    inbox, lib, _ = env
    client.put("/api/settings", json={"conflict_policy": "keep_larger"})
    old = _existing(lib, b"0123456789")
    make(inbox, MATRIX, b"tiny")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    res = client.post(f"/api/organize/items/{item['id']}/execute").json()
    assert res["status"] == "skipped" and old.read_bytes() == b"0123456789"


def test_tv_layout(client, env):
    inbox, lib, _ = env
    make(inbox, "Breaking.Bad.S02E05.720p.mkv")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    assert item["target_path"] == str(
        lib / "影集/絕命毒師 (2008)/Season 02/絕命毒師 - S02E05.mkv"
    )


def test_sample_and_hidden_ignored(client, env):
    inbox, _, _ = env
    make(inbox, "Movie.Sample.mkv")
    make(inbox, ".hidden/The.Matrix.1999.mkv")
    make(inbox, "notes.txt")
    assert client.post("/api/organize/scan").json()["created"] == 0


def test_ai_choice_requires_review_when_disabled(client, env):
    inbox, _, state = env
    client.put("/api/settings", json={"ai_auto_apply": False})
    state["ai"] = FakeAi({"tmdb_id": 2, "confidence": 0.95, "reason": "新版"})
    make(inbox, "Dune.1080p.mkv")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    assert item["status"] == "pending_review"
    assert item["method"] == "ai" and item["target_path"] != ""


def test_skip_and_scan_ignores(client, env):
    inbox, _, _ = env
    make(inbox, MATRIX)
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]
    assert client.post(f"/api/organize/items/{item['id']}/skip").json()["status"] == "skipped"
    assert client.post(f"/api/organize/items/{item['id']}/execute").status_code == 422


def test_execute_all(client, env):
    inbox, lib, _ = env
    make(inbox, MATRIX)
    make(inbox, "Breaking.Bad.S02E05.720p.mkv")
    client.post("/api/organize/scan")
    res = client.post("/api/organize/execute").json()
    assert res == {"done": 2, "skipped": 0, "failed": 0}


def test_hardlink_cross_device_error_message(tmp_path):
    from app.services.fileops import place

    a = tmp_path / "a"
    a.write_text("x")
    with pytest.raises(FileOpError):
        place("bogus", a, tmp_path / "b")
    place("copy", a, tmp_path / "b")
    with pytest.raises(FileOpError):
        place("copy", a, tmp_path / "b")


def test_ensure_within(tmp_path):
    ensure_within(tmp_path / "a/b", tmp_path)
    with pytest.raises(FileOpError):
        ensure_within(tmp_path / "../x", tmp_path)


def test_unconfigured_paths(client):
    app.dependency_overrides[tmdb_client] = lambda: None
    try:
        assert client.post("/api/organize/scan").status_code == 400
    finally:
        app.dependency_overrides.pop(tmdb_client, None)


def test_failure_rolls_back_main_file(client, env, monkeypatch):
    from app.services import fileops

    inbox, lib, _ = env
    make(inbox, MATRIX)
    make(inbox, "The.Matrix.1999.1080p.BluRay.x264.zh.srt", b"sub")
    client.post("/api/organize/scan")
    item = client.get("/api/organize/items").json()[0]

    real = fileops.place
    calls = []

    def flaky(mode, src, dst):
        calls.append(dst)
        if len(calls) == 2:
            raise FileOpError("模擬失敗")
        real(mode, src, dst)

    monkeypatch.setattr(fileops, "place", flaky)
    res = client.post(f"/api/organize/items/{item['id']}/execute").json()
    assert res["status"] == "failed" and "模擬失敗" in res["error"]
    assert not (lib / "電影").exists()
