def test_list_dirs(client, tmp_path):
    (tmp_path / "b").mkdir()
    (tmp_path / "A").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "file.txt").write_text("x")
    res = client.get("/api/fs/dirs", params={"path": str(tmp_path)}).json()
    assert res["dirs"].index("A") < res["dirs"].index("b")
    assert ".hidden" not in res["dirs"]
    assert "file.txt" not in res["dirs"]
    assert res["parent"] == str(tmp_path.parent)


def test_list_dirs_errors(client, tmp_path):
    assert client.get("/api/fs/dirs", params={"path": "relative"}).status_code == 422
    missing = str(tmp_path / "nope")
    assert client.get("/api/fs/dirs", params={"path": missing}).status_code == 404


def test_default_home(client):
    assert client.get("/api/fs/dirs").status_code == 200
