import asyncio

import httpx
import pytest
from sqlmodel import Session

from app import db
from app.services import chat_notify, watcher

HOOK = "https://discord.com/api/webhooks/123/abc-DEF_1"
RESULTS = [
    {"id": 1, "source": "A.mkv", "status": "done", "target": "電影/A (2020)/A.mkv"},
    {"id": 2, "source": "B.mkv", "status": "pending_review", "reason": "AI 無法確定"},
]
CFG = {
    "telegram_enabled": True,
    "telegram_token": "123:SECRET",
    "telegram_chat_id": "42",
    "discord_enabled": True,
    "discord_webhook": HOOK,
}


class Calls(list):
    state: dict


@pytest.fixture
def calls(monkeypatch):
    log = Calls()
    state = {"status": 200}

    def handler(request):
        log.append(request)
        if state["status"] == 0:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(state["status"])

    monkeypatch.setattr(
        chat_notify, "make_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    log.state = state
    return log


def run_notify(results):
    async def go():
        with Session(db.get_engine()) as s:
            return await chat_notify.notify(s, results)

    return asyncio.run(go())


def test_notify_both_channels(client, calls):
    assert client.put("/api/settings", json=CFG).status_code == 200
    assert run_notify(RESULTS) == []
    urls = [str(r.url) for r in calls]
    assert "https://api.telegram.org/bot123:SECRET/sendMessage" in urls
    assert HOOK in urls
    body = next(r for r in calls if r.url.host == "api.telegram.org").content.decode()
    assert "電影/A (2020)/A.mkv" in body and "待確認" in body


def test_disabled_and_empty(client, calls):
    client.put("/api/settings", json={**CFG, "telegram_enabled": False,
                                      "discord_enabled": False})
    assert run_notify(RESULTS) == []
    assert calls == []
    client.put("/api/settings", json=CFG)
    assert run_notify([]) == []
    assert calls == []


def test_secrets_masked(client):
    data = client.put("/api/settings", json=CFG).json()
    assert data["telegram_token"] == "****CRET"
    assert "abc" not in data["discord_webhook"]
    assert data["telegram_chat_id"] == "42"


def test_webhook_validation(client):
    res = client.put("/api/settings", json={"discord_webhook": "http://evil.test/x"})
    assert res.status_code == 422


def test_test_endpoints(client, calls):
    assert client.post("/api/settings/test/telegram").json()["ok"] is False
    client.put("/api/settings", json=CFG)
    assert client.post("/api/settings/test/telegram").json()["ok"] is True
    assert client.post("/api/settings/test/discord").json()["ok"] is True
    calls.state["status"] = 401
    res = client.post("/api/settings/test/telegram").json()
    assert res["ok"] is False and "401" in res["message"]
    calls.state["status"] = 0
    res = client.post("/api/settings/test/telegram").json()
    assert res["ok"] is False and "SECRET" not in res["message"]


def test_digest_error_recorded(client, calls):
    client.put("/api/settings", json=CFG)
    calls.state["status"] = 500

    async def go():
        with Session(db.get_engine()) as s:
            await watcher.send_digest(s, RESULTS)

    asyncio.run(go())
    assert "Telegram" in watcher.status.last_mail_error
    assert "Discord" in watcher.status.last_mail_error
    calls.state["status"] = 200
    asyncio.run(go())
    assert watcher.status.last_mail_error == ""


def test_long_text_clipped(client, calls):
    client.put("/api/settings", json=CFG)
    big = [{"id": i, "source": f"{'x' * 100}{i}.mkv", "status": "done", "target": "t"}
           for i in range(100)]
    run_notify(big)
    hook = next(r for r in calls if r.url.host == "discord.com")
    assert len(httpx.Response(200, content=hook.content).json()["content"]) <= 2000
