import shutil
import subprocess
import time

import pytest
from sqlmodel import Session

from app import db
from app.models import MediaItem
from app.services import transcode

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="需要 ffmpeg"
)


def make_video(path, vcodec="libx264", acodec="aac", extra=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=duration=6:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=duration=6",
            "-c:v", vcodec, "-pix_fmt", "yuv420p", "-c:a", acodec, *extra, str(path),
        ],
        check=True,
    )


@pytest.fixture
def lib(client, tmp_path):
    inbox, lib = tmp_path / "inbox", tmp_path / "lib"
    inbox.mkdir()
    lib.mkdir()
    client.put(
        "/api/library/paths", json={"inbox_path": str(inbox), "library_path": str(lib)}
    )
    yield lib
    transcode.kill_all_sync()


def add_item(path, status="done"):
    with Session(db.get_engine()) as s:
        item = MediaItem(
            source_path=f"/in/{path.name}", status=status, media_type="movie",
            tmdb_id=1, title="測試", target_path=str(path),
        )
        s.add(item)
        s.commit()
        return item.id


def start(client, item_id, **body):
    return client.post(f"/api/play/{item_id}/hls", json=body)


def test_status_available(client):
    data = client.get("/api/transcode/status").json()
    assert data["available"] is True and data["ffmpeg"]


def test_mp4_h264_aac_is_direct(client, lib):
    f = lib / "a.mp4"
    make_video(f)
    res = start(client, add_item(f)).json()
    assert res["mode"] == "direct" and res["session_id"] is None
    assert "/api/stream/" in res["direct_url"] and res["duration"] > 5


def test_mkv_h264_is_remuxed(client, lib):
    f = lib / "a.mkv"
    make_video(f)
    res = start(client, add_item(f)).json()
    assert res["mode"] == "remux" and res["session_id"]
    playlist = client.get(res["playlist_url"])
    assert playlist.status_code == 200
    assert playlist.text.startswith("#EXTM3U") and "seg_00000.ts" in playlist.text
    seg = client.get(f"/api/hls/{res['session_id']}/seg_00000.ts")
    assert seg.status_code == 200 and seg.content[0] == 0x47


@pytest.mark.skipif(
    "libx265" not in subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True
    ).stdout,
    reason="需要 libx265",
)
def test_hevc_is_transcoded(client, lib):
    f = lib / "h.mkv"
    make_video(f, vcodec="libx265", extra=("-x265-params", "log-level=none"))
    res = start(client, add_item(f)).json()
    assert res["mode"] == "transcode"
    assert client.get(res["playlist_url"]).status_code == 200


def test_non_aac_audio_gets_reencoded(client, lib):
    f = lib / "m.mkv"
    make_video(f, acodec="libmp3lame")
    res = start(client, add_item(f)).json()
    assert res["mode"] == "remux"
    seg = client.get(f"/api/hls/{res['session_id']}/seg_00000.ts")
    assert seg.status_code == 200


def test_session_reused_and_stopped(client, lib):
    f = lib / "a.mkv"
    make_video(f)
    item_id = add_item(f)
    first = start(client, item_id).json()
    assert start(client, item_id).json()["session_id"] == first["session_id"]
    sess = transcode.sessions[first["session_id"]]
    assert client.delete(f"/api/hls/{first['session_id']}").status_code == 204
    assert not sess.dir.exists()
    assert client.get(first["playlist_url"]).status_code == 404


def test_start_offset_makes_new_session(client, lib):
    f = lib / "a.mkv"
    make_video(f)
    item_id = add_item(f)
    a = start(client, item_id).json()
    b = start(client, item_id, start=2).json()
    assert a["session_id"] != b["session_id"]


def test_lru_eviction(client, lib, monkeypatch):
    monkeypatch.setattr(transcode, "MAX_SESSIONS", 1)
    f1, f2 = lib / "1.mkv", lib / "2.mkv"
    make_video(f1)
    make_video(f2)
    a = start(client, add_item(f1)).json()
    b = start(client, add_item(f2)).json()
    assert a["session_id"] not in transcode.sessions
    assert b["session_id"] in transcode.sessions


def test_file_name_whitelist(client, lib):
    f = lib / "a.mkv"
    make_video(f)
    sid = start(client, add_item(f)).json()["session_id"]
    for name in ["ffmpeg.log", "seg_1.ts", "..%2Findex.m3u8", "index.m3u8.bak"]:
        assert client.get(f"/api/hls/{sid}/{name}").status_code == 404
    assert client.get("/api/hls/unknown/index.m3u8").status_code == 404


def test_reaper_removes_idle(client, lib):
    f = lib / "a.mkv"
    make_video(f)
    sid = start(client, add_item(f)).json()["session_id"]
    sess = transcode.sessions[sid]
    assert client.post(f"/api/hls/{sid}/keepalive").status_code == 200
    import asyncio

    assert asyncio.run(transcode.reap_once(time.monotonic())) == 0
    assert sess.dir.exists()
    sess.last_access -= 10_000
    killed = asyncio.run(transcode.reap_once(time.monotonic()))
    assert killed == 1 and sid not in transcode.sessions


def test_not_playable_and_corrupt(client, lib):
    assert start(client, 9999).status_code == 404
    bad = lib / "bad.mkv"
    bad.write_bytes(b"not a video")
    assert start(client, add_item(bad)).status_code == 502
    pending = lib / "p.mkv"
    make_video(pending)
    assert start(client, add_item(pending, status="planned")).status_code == 404


def test_no_ffmpeg_returns_503(client, lib, monkeypatch):
    f = lib / "a.mkv"
    make_video(f)
    monkeypatch.setattr(transcode, "find_binaries", lambda s: None)
    assert start(client, add_item(f)).status_code == 503
    assert client.get("/api/transcode/status").json()["available"] is False


def test_ffmpeg_path_setting_validated(client):
    assert client.put("/api/settings", json={"ffmpeg_path": "/nope/ffmpeg"}).status_code == 422
    path = shutil.which("ffmpeg")
    res = client.put("/api/settings", json={"ffmpeg_path": path})
    assert res.json()["ffmpeg_path"] == path
    assert client.put("/api/settings", json={"ffmpeg_path": ""}).status_code == 200


def test_decide_rules():
    video = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}
    aac = {"codec_type": "audio", "codec_name": "aac"}
    ac3 = {"codec_type": "audio", "codec_name": "ac3"}
    assert transcode.decide({"streams": [video, aac]}, ".mp4")[0] == "direct"
    assert transcode.decide({"streams": [video, ac3]}, ".mp4") == ("remux", "aac")
    assert transcode.decide({"streams": [video, aac]}, ".mkv") == ("remux", "copy")
    ten_bit = {**video, "pix_fmt": "yuv420p10le"}
    assert transcode.decide({"streams": [ten_bit, aac]}, ".mp4")[0] == "transcode"
    hevc = {**video, "codec_name": "hevc"}
    assert transcode.decide({"streams": [hevc, aac]}, ".mp4")[0] == "transcode"
    with pytest.raises(transcode.TranscodeError):
        transcode.decide({"streams": [aac]}, ".mp4")


def test_cached_item_skips_session(client, lib, tmp_path, monkeypatch):
    import asyncio

    from app.config import settings
    from app.services import precache

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    f = lib / "c.mkv"
    make_video(f, vcodec="mpeg4")
    item_id = add_item(f)
    asyncio.run(precache.precache("ffmpeg", "ffprobe", item_id, f))
    res = start(client, item_id, start=3).json()
    assert res["cached"] is True and res["session_id"] is None
    assert not transcode.sessions
    playlist = client.get(res["playlist_url"])
    assert playlist.status_code == 200 and "#EXT-X-ENDLIST" in playlist.text
    seg = client.get(f"/api/hls/cache/{item_id}/seg_00000.ts")
    assert seg.status_code == 200 and seg.content[0] == 0x47
    assert client.get(f"/api/hls/cache/{item_id}/..%2Fmeta.json").status_code == 404
