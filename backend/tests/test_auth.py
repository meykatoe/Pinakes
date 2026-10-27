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


def test_throttle_retry_after(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    client.cookies.clear()
    for _ in range(auth.MAX_FAILS):
        client.post("/api/auth/login", json={"password": "bad"})
    res = client.post("/api/auth/login", json={"password": "secret123"})
    assert res.status_code == 429
    assert 0 < int(res.headers["Retry-After"]) <= auth.FAIL_WINDOW


def test_success_resets_fails(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    client.cookies.clear()
    for _ in range(auth.MAX_FAILS - 1):
        client.post("/api/auth/login", json={"password": "bad"})
    assert client.post("/api/auth/login", json={"password": "secret123"}).status_code == 200
    for _ in range(auth.MAX_FAILS - 1):
        client.post("/api/auth/login", json={"password": "bad"})
    assert client.post("/api/auth/login", json={"password": "secret123"}).status_code == 200


def test_unlock_after_window():
    auth._fails.clear()
    for _ in range(auth.MAX_FAILS):
        auth.record_fail("1.2.3.4", now=1000)
    assert auth.throttled("1.2.3.4", now=1001)
    assert auth.retry_after("1.2.3.4", now=1001) == auth.FAIL_WINDOW
    assert not auth.throttled("1.2.3.4", now=1000 + auth.FAIL_WINDOW)


def test_throttle_is_per_ip():
    auth._fails.clear()
    for _ in range(auth.MAX_FAILS):
        auth.record_fail("1.1.1.1", now=1000)
    assert auth.throttled("1.1.1.1", now=1001)
    assert not auth.throttled("2.2.2.2", now=1001)


def test_stale_ips_pruned():
    auth._fails.clear()
    auth.record_fail("1.1.1.1", now=1000)
    auth.record_fail("2.2.2.2", now=1000 + auth.FAIL_WINDOW + 1)
    assert list(auth._fails) == ["2.2.2.2"]


def test_change_password_throttled(client):
    client.put("/api/auth/password", json={"new": "secret123"})
    for _ in range(auth.MAX_FAILS):
        res = client.put("/api/auth/password", json={"current": "bad", "new": "other123"})
        assert res.status_code == 422
    res = client.put("/api/auth/password", json={"current": "secret123", "new": "other123"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers


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
