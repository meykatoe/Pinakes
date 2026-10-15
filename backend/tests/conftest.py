import pytest
from fastapi.testclient import TestClient

from app import db, security
from app.config import settings
from app.main import app
from app.services import auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "watch_loop", False)
    db.get_engine.cache_clear()
    security._fernet.cache_clear()
    security._key.cache_clear()
    auth._fails.clear()
    with TestClient(app) as c:
        yield c
    db.get_engine.cache_clear()
    security._fernet.cache_clear()
    security._key.cache_clear()
