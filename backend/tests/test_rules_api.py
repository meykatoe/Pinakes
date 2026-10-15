RULE = {"name": "ep", "pattern": r"^(?P<title>.+?) EP(?P<episode>\d+)", "media_type": "tv"}


def test_rule_crud(client):
    res = client.post("/api/rules", json=RULE)
    assert res.status_code == 201
    rid = res.json()["id"]
    upd = {**RULE, "priority": 5}
    assert client.put(f"/api/rules/{rid}", json=upd).json()["priority"] == 5
    assert len(client.get("/api/rules").json()) == 1
    assert client.delete(f"/api/rules/{rid}").status_code == 204


def test_rule_invalid(client):
    assert client.post("/api/rules", json={**RULE, "pattern": "("}).status_code == 422
    assert client.post("/api/rules", json={**RULE, "pattern": r"\d"}).status_code == 422
    assert client.post("/api/rules", json={**RULE, "media_type": "x"}).status_code == 422


def test_naming_defaults_and_update(client):
    data = client.get("/api/naming").json()
    assert "{title}" in data["movie_template"]
    bad = {**data, "tv_template": "{nope}"}
    assert client.put("/api/naming", json=bad).status_code == 422
    good = {**data, "movie_template": "{title}"}
    assert client.put("/api/naming", json=good).json()["movie_template"] == "{title}"


def test_preview_default(client):
    res = client.post(
        "/api/parse/preview", json={"path": "Breaking.Bad.S02E05.720p.mkv"}
    ).json()
    assert res["target"] == "Breaking Bad/Season 02/Breaking Bad - S02E05.mkv"


def test_preview_with_rule(client):
    client.post("/api/rules", json=RULE)
    res = client.post("/api/parse/preview", json={"path": "My_Show EP12.mp4"}).json()
    assert res["rule"] == "ep"
    assert res["target"] == "My Show/Season 01/My Show - S01E12.mp4"
