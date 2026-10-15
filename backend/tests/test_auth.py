from app.services import auth


def test_open_when_no_password(client):
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/auth/status").json() == {
        "enabled": False, "authenticated": True,
    }


def test_set_password_and_login(client):
    res = client.put("/api/auth/password", json={"new": "secret123"})
    assert res.json() == {"enabled": True, "authenticated": True}
    assert client.get("/api/settings").status_code == 200

    client.cookies.clear()
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/status").json()["authenticated"] is False

    assert client.post("/api/auth/login", json={"password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"password": "secret123"}).status_code == 200
    assert client.get("/api/settings").status_code == 200


def test_short_password_rejected(client):
    assert client.put("/api/auth/password", json={"new": "123"}).status_code == 422


def test_change_requires_current(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    res = client.put("/api/auth/password", json={"current": "x", "new": "other456"})
    assert res.status_code == 422
    res = client.put(
        "/api/auth/password", json={"current": "secret123", "new": "other456"}
    )
    assert res.status_code == 200
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"password": "other456"}).status_code == 200


def test_disable_password(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    res = client.put("/api/auth/password", json={"current": "secret123", "new": ""})
    assert res.json()["enabled"] is False
    client.cookies.clear()
    assert client.get("/api/settings").status_code == 200


def test_change_requires_login(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    client.cookies.clear()
    res = client.put("/api/auth/password", json={"current": "secret123", "new": ""})
    assert res.status_code == 401


def test_throttle(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    client.cookies.clear()
    for _ in range(auth.MAX_FAILS):
        client.post("/api/auth/login", json={"password": "bad"})
    res = client.post("/api/auth/login", json={"password": "secret123"})
    assert res.status_code == 429


def test_token_expiry_and_tamper():
    stored = auth.hash_password("pw123456")
    token = auth.make_token(stored, now=1000)
    assert auth.check_token(token, stored, now=1001)
    assert not auth.check_token(token, stored, now=1000 + auth.MAX_AGE + 1)
    assert not auth.check_token(token + "0", stored, now=1001)
    assert not auth.check_token(token, auth.hash_password("pw123456"), now=1001)


def test_password_hash_roundtrip():
    stored = auth.hash_password("hello world")
    assert auth.verify_password("hello world", stored)
    assert not auth.verify_password("hello", stored)
    assert not auth.verify_password("x", "garbage")


def test_cli_reset(client, capsys):
    from app.cli import main

    client.put("/api/auth/password", json={"new": "secret123"})
    assert main(["reset-password"]) == 0
    client.cookies.clear()
    assert client.get("/api/settings").status_code == 200
