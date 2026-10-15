import shutil

import pytest

from tests.test_hls import add_item, lib, make_video  # noqa: F401

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="需要 ffmpeg")

SRT = "1\n00:00:01,000 --> 00:00:03,000\n你好\n\n2\n00:00:05,000 --> 00:00:06,000\n再見\n"


def test_list_and_convert(client, lib):  # noqa: F811
    video = lib / "a.mkv"
    make_video(video)
    (lib / "a.zh-TW.srt").write_bytes(SRT.encode("big5"))
    (lib / "a.en.srt").write_text(SRT.replace("你好", "Hi").replace("再見", "Bye"))
    item_id = add_item(video)
    subs = client.get(f"/api/play/{item_id}/subtitles").json()
    assert [s["label"] for s in subs] == ["en", "zh-TW"]
    res = client.get(f"/api/play/{item_id}/subtitles/1.vtt")
    assert res.status_code == 200
    assert res.text.startswith("WEBVTT") and "你好" in res.text
    shifted = client.get(f"/api/play/{item_id}/subtitles/1.vtt", params={"offset": 4})
    assert "你好" not in shifted.text and "再見" in shifted.text


def test_missing_subtitle(client, lib):  # noqa: F811
    video = lib / "b.mkv"
    make_video(video)
    item_id = add_item(video)
    assert client.get(f"/api/play/{item_id}/subtitles").json() == []
    assert client.get(f"/api/play/{item_id}/subtitles/0.vtt").status_code == 404
