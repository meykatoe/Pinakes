import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import mount_frontend


@pytest.fixture
def web(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>")
    (tmp_path / "assets" / "a.js").write_text("js")
    (tmp_path.parent / "secret.txt").write_text("no")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    return TestClient(app)


def test_index_and_fallback(web):
    assert web.get("/").text == "<html>app</html>"
    assert web.get("/organize").text == "<html>app</html>"


def test_asset_cached(web):
    res = web.get("/assets/a.js")
    assert res.text == "js"
    assert "immutable" in res.headers["cache-control"]


def test_api_not_swallowed(web):
    assert web.get("/api/nothing").status_code == 404


def test_no_traversal(web):
    assert web.get("/..%2Fsecret.txt").text == "<html>app</html>"


def test_missing_build(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "none")
    assert TestClient(app).get("/").status_code == 404
