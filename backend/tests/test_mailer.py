import asyncio
import smtplib

import pytest
from sqlmodel import Session

from app import db
from app.services import mailer, watcher

CFG = {
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_user": "me@example.com",
    "smtp_password": "secret-pass",
    "smtp_security": "starttls",
    "notify_to": "you@example.com",
    "notify_enabled": True,
}


class FakeSMTP:
    sent: list = []
    log: list = []
    fail_login = False
    fail_connect = False

    def __init__(self, host, port, timeout=None, context=None):
        if FakeSMTP.fail_connect:
            raise ConnectionRefusedError()
        FakeSMTP.log.append(("connect", host, port, type(self).__name__))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        FakeSMTP.log.append(("starttls",))

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad")
        FakeSMTP.log.append(("login", user, password))

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


class FakeSSL(FakeSMTP):
    pass


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.log = [], []
    FakeSMTP.fail_login = FakeSMTP.fail_connect = False
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSSL)


def configure(client, **extra):
    res = client.put("/api/settings", json={**CFG, **extra})
    assert res.status_code == 200
    return res.json()


def test_settings_masked_and_validated(client):
    data = configure(client)
    assert data["smtp_password"] == "****pass"
    assert data["smtp_port"] == 587 and data["notify_enabled"] is True
    assert client.put("/api/settings", json={"notify_to": "bad"}).status_code == 422
    assert client.put("/api/settings", json={"smtp_port": 0}).status_code == 422
    assert client.put("/api/settings", json={"smtp_security": "x"}).status_code == 422
    assert client.put("/api/settings", json={"notify_to": ""}).status_code == 200


def test_smtp_test_endpoint(client):
    configure(client)
    res = client.post("/api/settings/test/smtp").json()
    assert res["ok"] is True
    assert ("starttls",) in FakeSMTP.log
    assert ("login", "me@example.com", "secret-pass") in FakeSMTP.log
    assert FakeSMTP.sent[0]["To"] == "you@example.com"


def test_ssl_mode_skips_starttls(client):
    configure(client, smtp_security="ssl", smtp_port=465)
    client.post("/api/settings/test/smtp")
    assert ("starttls",) not in FakeSMTP.log
    assert FakeSMTP.log[0][3] == "FakeSSL"


def test_test_endpoint_errors(client):
    assert client.post("/api/settings/test/smtp").json()["ok"] is False
    configure(client)
    FakeSMTP.fail_login = True
    res = client.post("/api/settings/test/smtp").json()
    assert res["ok"] is False and "帳號或密碼" in res["message"]
    assert "secret-pass" not in res["message"]
    FakeSMTP.fail_login, FakeSMTP.fail_connect = False, True
    assert client.post("/api/settings/test/smtp").json()["ok"] is False


RESULTS = [
    {"id": 1, "source": "A <b>.mkv", "status": "done", "target": "電影/A (2020)/A.mkv"},
    {"id": 2, "source": "B.mkv", "status": "pending_review", "reason": "AI 無法確定"},
    {"id": 3, "source": "C.mkv", "status": "failed", "error": "目標已存在"},
]


def run_notify(results):
    async def go():
        with Session(db.get_engine()) as s:
            await mailer.notify(s, results)

    asyncio.run(go())


def test_digest_content(client):
    configure(client)
    run_notify(RESULTS)
    msg = FakeSMTP.sent[0]
    assert "已整理 1 項" in msg["Subject"] and "失敗 1 項" in msg["Subject"]
    body = msg.get_body(("plain",)).get_content()
    assert "電影/A (2020)/A.mkv" in body and "AI 無法確定" in body
    html_body = msg.get_body(("html",)).get_content()
    assert "&lt;b&gt;" in html_body and "<b>" not in html_body.replace("<body>", "")


def test_notify_disabled_or_empty(client):
    configure(client, notify_enabled=False)
    run_notify(RESULTS)
    assert FakeSMTP.sent == []
    configure(client, notify_enabled=True)
    run_notify([])
    assert FakeSMTP.sent == []


def test_digest_failure_recorded_not_raised(client):
    configure(client)
    FakeSMTP.fail_connect = True

    async def go():
        with Session(db.get_engine()) as s:
            await watcher.send_digest(s, RESULTS)

    asyncio.run(go())
    assert "寄信失敗" in watcher.status.last_mail_error
    FakeSMTP.fail_connect = False
    asyncio.run(go())
    assert watcher.status.last_mail_error == ""
