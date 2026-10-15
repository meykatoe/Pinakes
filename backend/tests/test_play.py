from urllib.parse import parse_qs, quote, urlparse

import pytest
from sqlmodel import Session

from app import db
from app.models import MediaItem
from app.services import player

DATA = bytes(range(256)) * 40


@pytest.fixture
def lib_item(client, tmp_path):
    inbox, lib = tmp_path / "inbox", tmp_path / "lib"
    inbox.mkdir()
    lib.mkdir()
    client.put(
        "/api/library/paths", json={"inbox_path": str(inbox), "library_path": str(lib)}
    )
    target = lib / "電影" / "駭客任務 (1999)" / "駭客任務 (1999).mkv"
    target.parent.mkdir(parents=True)
    target.write_bytes(DATA)
    with Session(db.get_engine()) as s:
        item = MediaItem(
            source_path="/in/x.mkv", status="done", media_type="movie", tmdb_id=603,
            title="駭客任務", target_path=str(target),
        )
        s.add(item)
        s.commit()
        return item.id, target


def links(client, item_id):
    res = client.get(f"/api/play/{item_id}")
    assert res.status_code == 200
    return res.json()


def stream_path(stream_url):
    parts = urlparse(stream_url)
    return f"{parts.path}?{parts.query}"


def test_presets_seeded(client):
    names = [p["name"] for p in client.get("/api/players").json()]
    assert names == ["PotPlayer", "VLC", "IINA", "下載 m3u 清單"]


def test_play_links_use_stream_url(client, lib_item):
    item_id, _ = lib_item
    data = links(client, item_id)
    by_name = {l["name"]: l for l in data["links"]}
    assert by_name["PotPlayer"]["href"] == "potplayer://" + data["stream_url"]
    assert by_name["VLC"]["href"].startswith("vlc://http://")
    assert by_name["IINA"]["href"] == "iina://weblink?url=" + quote(
        data["stream_url"], safe=""
    )
    assert by_name["下載 m3u 清單"]["href"].endswith(
        f"/api/stream/{item_id}/playlist.m3u?token=" + parse_qs(
            urlparse(data["stream_url"]).query
        )["token"][0]
    )


def test_stream_full_and_range(client, lib_item):
    item_id, _ = lib_item
    url = stream_path(links(client, item_id)["stream_url"])
    full = client.get(url)
    assert full.status_code == 200 and full.content == DATA
    assert full.headers["content-type"] == "video/x-matroska"
    part = client.get(url, headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == DATA[10:20]
    assert part.headers["content-range"] == f"bytes 10-19/{len(DATA)}"
    assert client.head(url).status_code == 200


def test_stream_requires_token(client, lib_item):
    item_id, _ = lib_item
    url = stream_path(links(client, item_id)["stream_url"])
    base = url.split("?")[0]
    assert client.get(base).status_code == 403
    assert client.get(base + "?token=wrong").status_code == 403


def test_regenerate_token_invalidates(client, lib_item):
    item_id, _ = lib_item
    old = stream_path(links(client, item_id)["stream_url"])
    client.post("/api/play/token/regenerate")
    assert client.get(old).status_code == 403
    assert client.get(stream_path(links(client, item_id)["stream_url"])).status_code == 200


def test_playlist(client, lib_item):
    item_id, _ = lib_item
    data = links(client, item_id)
    m3u = next(l for l in data["links"] if l["kind"] == "m3u")["href"]
    res = client.get(stream_path(m3u))
    assert res.status_code == 200
    lines = res.text.splitlines()
    assert lines[0] == "#EXTM3U" and lines[1] == "#EXTINF:-1,駭客任務"
    assert lines[2] == data["stream_url"]
    assert "attachment" in res.headers["content-disposition"]


def test_only_done_and_inside_library(client, lib_item, tmp_path):
    item_id, _ = lib_item
    outside = tmp_path / "secret.mkv"
    outside.write_bytes(b"x")
    with Session(db.get_engine()) as s:
        evil = MediaItem(
            source_path="/in/y", status="done", media_type="movie", tmdb_id=1,
            target_path=str(outside),
        )
        pending = MediaItem(
            source_path="/in/z", status="planned", media_type="movie", tmdb_id=2,
            target_path=str(tmp_path / "lib" / "電影" / "駭客任務 (1999)" / "駭客任務 (1999).mkv"),
        )
        s.add(evil)
        s.add(pending)
        s.commit()
        evil_id, pending_id = evil.id, pending.id
    assert client.get(f"/api/play/{evil_id}").status_code == 404
    assert client.get(f"/api/play/{pending_id}").status_code == 404
    assert client.get("/api/play/9999").status_code == 404


def test_missing_file_404(client, lib_item):
    item_id, target = lib_item
    target.unlink()
    assert client.get(f"/api/play/{item_id}").status_code == 404


def test_public_base_url_override(client, lib_item):
    item_id, _ = lib_item
    res = client.put("/api/settings", json={"public_base_url": "http://192.168.1.5:8000/"})
    assert res.json()["public_base_url"] == "http://192.168.1.5:8000"
    assert links(client, item_id)["stream_url"].startswith("http://192.168.1.5:8000/api/stream/")
    assert client.put("/api/settings", json={"public_base_url": "ftp://x"}).status_code == 422
    assert client.put("/api/settings", json={"public_base_url": ""}).status_code == 200


def test_player_crud_and_validation(client):
    ok = {"name": "MPV", "kind": "link", "template": "mpv://{url_encoded}"}
    res = client.post("/api/players", json=ok)
    assert res.status_code == 201
    pid = res.json()["id"]
    upd = client.put(f"/api/players/{pid}", json={**ok, "enabled": False})
    assert upd.json()["enabled"] is False
    assert client.delete(f"/api/players/{pid}").status_code == 204

    for bad in [
        {**ok, "template": "mpv://nothing"},
        {**ok, "template": "javascript:alert({url})"},
        {**ok, "template": "DATA:text/html,{url}"},
        {**ok, "template": "{url}"},
        {**ok, "kind": "exe"},
        {**ok, "name": " "},
    ]:
        assert client.post("/api/players", json=bad).status_code == 422


def test_disabled_player_hidden(client, lib_item):
    item_id, _ = lib_item
    vlc = next(p for p in client.get("/api/players").json() if p["name"] == "VLC")
    client.put(f"/api/players/{vlc['id']}", json={**vlc, "enabled": False})
    names = [l["name"] for l in links(client, item_id)["links"]]
    assert "VLC" not in names and "PotPlayer" in names


def test_build_href_placeholders():
    assert player.build_href("x://{url}|{filename}", "http://h/a b", "a b.mkv") == (
        "x://http://h/a b|a%20b.mkv"
    )
