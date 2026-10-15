import sqlite3

from sqlmodel import Session

from app import db
from app.config import settings
from app.models import MediaItem


def test_migrate_adds_missing_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db.get_engine.cache_clear()
    conn = sqlite3.connect(tmp_path / "pinakes.db")
    conn.execute("CREATE TABLE mediaitem (id INTEGER PRIMARY KEY, source_path VARCHAR)")
    conn.execute("INSERT INTO mediaitem (source_path) VALUES ('/a.mkv')")
    conn.commit()
    conn.close()
    try:
        db.init_db()
        with Session(db.get_engine()) as s:
            item = s.get(MediaItem, 1)
            assert item.status == "pending_review"
            assert item.candidates == "[]"
            assert item.size == 0
    finally:
        db.get_engine.cache_clear()


def test_wal_enabled(client):
    with db.get_engine().connect() as conn:
        mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
    assert mode == "wal"
