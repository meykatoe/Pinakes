import asyncio

import httpx
from sqlmodel import Session

from app import db
from app.models import Setting
from app.services.connectivity import check_openai, check_tmdb


def test_defaults(client):
    data = client.get("/api/settings").json()
    assert data["tmdb_api_key"] == ""
    assert data["tmdb_language"] == "zh-TW"


def test_secret_masked_and_encrypted(client):
    res = client.put("/api/settings", json={"tmdb_api_key": "abcdef123456"})
    assert res.json()["tmdb_api_key"] == "****3456"
    assert client.get("/api/settings").json()["tmdb_api_key"] == "****3456"
    with Session(db.get_engine()) as s:
        raw = s.get(Setting, "tmdb_api_key").value
    assert "abcdef" not in raw


def test_partial_update_keeps_other(client):
    client.put("/api/settings", json={"openai_api_key": "sk-test-9999"})
    client.put("/api/settings", json={"openai_model": "gpt-4o"})
    data = client.get("/api/settings").json()
    assert data["openai_api_key"] == "****9999"
    assert data["openai_model"] == "gpt-4o"


def test_connection_without_key(client):
    res = client.post("/api/settings/test/tmdb").json()
    assert res["ok"] is False


def _transport(status: int):
    return httpx.MockTransport(lambda req: httpx.Response(status))


def test_check_tmdb():
    assert asyncio.run(check_tmdb("k" * 32, _transport(200)))[0] is True
    assert asyncio.run(check_tmdb("k" * 32, _transport(401)))[0] is False


def test_check_openai():
    ok = asyncio.run(check_openai("sk", "https://x/v1", _transport(200)))
    bad = asyncio.run(check_openai("sk", "https://x/v1", _transport(401)))
    assert ok[0] is True
    assert bad[0] is False
