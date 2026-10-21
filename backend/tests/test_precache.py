import asyncio
import shutil

import pytest

from app.config import settings
from app.services import precache, transcode
from tests.test_hls import make_video

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 ffmpeg"
)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")


def test_transcode_is_cached(tmp_path):
    src = tmp_path / "a.mkv"
    make_video(src, vcodec="mpeg4")
    assert asyncio.run(precache.precache("ffmpeg", "ffprobe", 1, src)) is True
    assert precache.is_cached(1, src)
    assert (precache.cache_dir(1) / "index.m3u8").is_file()
    assert not (precache.cache_root() / "1.tmp").exists()


def test_direct_is_skipped(tmp_path):
    src = tmp_path / "a.mp4"
    make_video(src)
    assert asyncio.run(precache.precache("ffmpeg", "ffprobe", 2, src)) is False
    assert not precache.is_cached(2, src)


def test_changed_source_invalidates(tmp_path):
    src = tmp_path / "a.mkv"
    make_video(src, vcodec="mpeg4")
    asyncio.run(precache.precache("ffmpeg", "ffprobe", 3, src))
    src.write_bytes(src.read_bytes() + b"0")
    assert not precache.is_cached(3, src)


def test_bad_file_leaves_nothing(tmp_path):
    src = tmp_path / "a.mkv"
    src.write_bytes(b"junk")
    with pytest.raises(transcode.TranscodeError):
        asyncio.run(precache.precache("ffmpeg", "ffprobe", 4, src))
    assert not precache.cache_dir(4).exists()


def test_evict_oldest_first(tmp_path):
    import os

    for item_id, age in ((1, 100), (2, 200), (3, 300)):
        folder = precache.cache_dir(item_id)
        folder.mkdir(parents=True)
        (folder / "seg_00000.ts").write_bytes(b"x" * 100)
        meta = folder / "meta.json"
        meta.write_text("{}")
        os.utime(meta, (1000 + age, 1000 + age))
    assert precache.evict(250, keep=1) == 1
    assert precache.cache_dir(1).exists() and not precache.cache_dir(2).exists()
    assert precache.cache_dir(3).exists()


def test_request_ignored_when_disabled(client):
    from sqlmodel import Session

    from app.db import get_engine

    with Session(get_engine()) as session:
        precache.request(session, 1)
    assert precache.queued == set()


def test_settings_roundtrip(client):
    r = client.put(
        "/api/settings",
        json={"precache_enabled": True, "precache_max_gb": 20, "hwaccel": "off"},
    )
    body = r.json()
    assert body["precache_enabled"] is True and body["precache_max_gb"] == 20
    assert body["hwaccel"] == "off"


def test_run_requires_worker(client):
    assert client.post("/api/precache/run").status_code == 503


def test_run_enqueues_done_items(client, monkeypatch):
    import asyncio

    from sqlmodel import Session

    from app import db
    from app.models import MediaItem

    with Session(db.get_engine()) as s:
        for i, status in enumerate(("done", "done", "planned")):
            s.add(MediaItem(source_path=f"/in/{i}.mkv", status=status))
        s.commit()
    monkeypatch.setattr(precache, "queue", asyncio.Queue())
    monkeypatch.setattr(precache, "queued", set())
    assert client.post("/api/precache/run").json() == {"added": 2}
    assert client.post("/api/precache/run").json() == {"added": 0}
    data = client.get("/api/precache/status").json()
    assert data["queued"] == 2 and data["cached"] == 0
