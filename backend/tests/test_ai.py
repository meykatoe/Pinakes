import asyncio
import json

import httpx
import pytest
from sqlmodel import Session

from app import db
from app.api.match import ai_client, tmdb_client
from app.main import app
from app.services.ai import AiClient, AiError
from app.services.tmdb import TmdbClient
from tests.test_match import Fake


class FakeAi:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        content = json.dumps(self.reply)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def make_ai(session, fake_ai, limit=200):
    return AiClient(
        "sk", "https://x/v1", "m", session, limit, httpx.MockTransport(fake_ai.handler)
    )


@pytest.fixture
def setup(client):
    tm = Fake()
    holder = {}

    def tmdb():
        with Session(db.get_engine()) as s:
            return TmdbClient("k" * 32, "zh-TW", s, httpx.MockTransport(tm.handler))

    def ai():
        s = Session(db.get_engine())
        return make_ai(s, holder["ai"], holder.get("limit", 200))

    app.dependency_overrides[tmdb_client] = tmdb
    app.dependency_overrides[ai_client] = ai
    yield holder
    app.dependency_overrides.pop(tmdb_client, None)
    app.dependency_overrides.pop(ai_client, None)


def test_ai_picks_among_candidates(client, setup):
    setup["ai"] = FakeAi({"tmdb_id": 2, "confidence": 0.9, "reason": "較新版本"})
    res = client.post("/api/match/preview", json={"path": "Dune.1080p.mkv"}).json()
    assert res["chosen"]["tmdb_id"] == 2
    assert res["method"] == "ai" and res["reason"] == "較新版本"
    assert res["confident"] is True


def test_ai_low_confidence_rejected(client, setup):
    setup["ai"] = FakeAi({"tmdb_id": 2, "confidence": 0.3, "reason": "不確定"})
    res = client.post("/api/match/preview", json={"path": "Dune.1080p.mkv"}).json()
    assert res["chosen"] is None and res["reason"] == "不確定"


def test_ai_invented_id_rejected(client, setup):
    setup["ai"] = FakeAi({"tmdb_id": 999, "confidence": 1.0, "reason": "x"})
    res = client.post("/api/match/preview", json={"path": "Dune.1080p.mkv"}).json()
    assert res["chosen"] is None


def test_ai_rewrite_then_search(client, setup):
    setup["ai"] = FakeAi({"title": "The Matrix", "year": 1999})
    res = client.post("/api/match/preview", json={"path": "駭客任務.mkv"}).json()
    assert res["chosen"]["tmdb_id"] == 603
    assert res["method"] == "ai"


def test_rule_match_skips_ai(client, setup):
    setup["ai"] = FakeAi({})
    res = client.post(
        "/api/match/preview", json={"path": "The.Matrix.1999.1080p.mkv"}
    ).json()
    assert res["method"] == "rule" and setup["ai"].calls == 0


def test_ai_failure_degrades(client, setup):
    ai = FakeAi({})
    ai.handler = lambda req: httpx.Response(500)
    setup["ai"] = ai
    res = client.post("/api/match/preview", json={"path": "Dune.1080p.mkv"}).json()
    assert res["chosen"] is None and "AI 無法使用" in res["reason"]


def test_ai_cache_and_limit(client):
    fake = FakeAi({"title": "X", "year": None})
    with Session(db.get_engine()) as s:
        ai = make_ai(s, fake, limit=1)
        asyncio.run(ai.rewrite("a.mkv"))
        asyncio.run(ai.rewrite("a.mkv"))
        assert fake.calls == 1
        with pytest.raises(AiError):
            asyncio.run(ai.rewrite("b.mkv"))


def test_ai_settings_roundtrip(client):
    data = client.get("/api/settings").json()
    assert data["ai_enabled"] is True and data["ai_daily_limit"] == 200
    res = client.put("/api/settings", json={"ai_enabled": False, "ai_daily_limit": 50})
    assert res.json()["ai_enabled"] is False
    assert client.get("/api/settings").json()["ai_daily_limit"] == 50
    assert client.put("/api/settings", json={"ai_daily_limit": -1}).status_code == 422
