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
