from pathlib import Path

from app.services import hwaccel, transcode


def test_off_returns_none():
    assert hwaccel.detect("ffmpeg", "off") is None


def test_missing_ffmpeg_returns_none():
    hwaccel.reset()
    assert hwaccel.detect("/no/such/ffmpeg") is None


def test_build_command_uses_hw_encoder():
    cmd = transcode.build_command(
        "ffmpeg", Path("a.mkv"), "transcode", "aac", 0, Path("out"), "nvenc"
    )
    assert "h264_nvenc" in cmd and "libx264" not in cmd


def test_remux_ignores_hw():
    cmd = transcode.build_command(
        "ffmpeg", Path("a.mkv"), "remux", "aac", 0, Path("out"), "vaapi"
    )
    assert "-vaapi_device" not in cmd and "copy" in cmd


def test_software_by_default():
    cmd = transcode.build_command("ffmpeg", Path("a.mkv"), "transcode", "aac", 0, Path("o"))
    assert "libx264" in cmd
