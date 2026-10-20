def test_seeded_categories(client):
    names = [c["name"] for c in client.get("/api/categories").json()]
    assert names == ["電影", "影集"]


def test_paths_roundtrip(client, tmp_path):
    inbox, lib = tmp_path / "in", tmp_path / "lib"
    inbox.mkdir()
    lib.mkdir()
    res = client.put(
        "/api/library/paths",
        json={"inbox_path": str(inbox), "library_path": str(lib)},
    )
    assert res.status_code == 200
    assert res.json()["same_device"] is True
    assert client.get("/api/library/paths").json()["inbox_path"] == str(inbox)


def test_paths_invalid(client, tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()

    def put(i, b):
        return client.put(
            "/api/library/paths",
            json={"inbox_path": str(i), "library_path": str(b)},
        )

    assert put(tmp_path / "missing", lib).status_code == 422
    assert put(lib, lib).status_code == 422
    assert put(lib / "sub", lib).status_code == 422
    (lib / "sub").mkdir()
    assert put(lib / "sub", lib).status_code == 422


def test_category_crud(client):
    body = {"name": "動畫", "media_type": "tv", "subdir": "動畫"}
    res = client.post("/api/categories", json=body)
    assert res.status_code == 201
    cid = res.json()["id"]
    body["subdir"] = "日本/動畫"
    assert client.put(f"/api/categories/{cid}", json=body).json()["subdir"] == "日本/動畫"
    assert client.delete(f"/api/categories/{cid}").status_code == 204


def test_category_rules(client):
    dup = {"name": "電影", "media_type": "movie", "subdir": "x"}
    assert client.post("/api/categories", json=dup).status_code == 409
    bad = {"name": "A", "media_type": "tv", "subdir": "../etc"}
    assert client.post("/api/categories", json=bad).status_code == 422
    bad["subdir"] = "/abs"
    assert client.post("/api/categories", json=bad).status_code == 422
    bad = {"name": "A", "media_type": "game", "subdir": "a"}
    assert client.post("/api/categories", json=bad).status_code == 422


def test_builtin_protected(client):
    movie = client.get("/api/categories").json()[0]
    assert client.delete(f"/api/categories/{movie['id']}").status_code == 422
    body = {"name": "電影", "media_type": "tv", "subdir": "電影"}
    assert client.put(f"/api/categories/{movie['id']}", json=body).status_code == 422
