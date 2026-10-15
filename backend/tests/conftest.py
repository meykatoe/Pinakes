import pytest
from fastapi.testclient import TestClient

from app import db, security
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db.get_engine.cache_clear()
    security._fernet.cache_clear()
    with TestClient(app) as c:
        yield c
    db.get_engine.cache_clear()
    security._fernet.cache_clear()
