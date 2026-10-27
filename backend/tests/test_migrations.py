import sqlite3

import pytest
from sqlalchemy import text

from app import db, migrations
from app.config import settings


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db.get_engine.cache_clear()
    yield db.get_engine()
    db.get_engine.cache_clear()


def seed(path, sql: list[str]) -> None:
    conn = sqlite3.connect(path)
    for stmt in sql:
        conn.execute(stmt)
    conn.commit()
    conn.close()


def version(engine) -> int:
    return migrations.current_version(engine)


def test_fresh_db_stamped_latest(engine):
    steps = [lambda c: None, lambda c: None]
    assert migrations.upgrade(engine, True, steps) == 2
    assert version(engine) == 2
    assert not list(settings.data_dir.glob("*.bak"))


def test_init_db_creates_version_table(engine):
    db.init_db()
    assert version(engine) == len(migrations.MIGRATIONS)


def test_legacy_db_runs_all_in_order(engine):
    seed(settings.data_dir / "pinakes.db", ["CREATE TABLE t (id INTEGER, old TEXT)"])
    seed(settings.data_dir / "pinakes.db", ["INSERT INTO t VALUES (1, 'x')"])
    order = []

    def rename(conn):
        order.append(1)
        migrations.rename_column(conn, "t", "old", "new")

    def drop(conn):
        order.append(2)
        conn.execute(text("ALTER TABLE t ADD COLUMN extra TEXT"))
        migrations.drop_column(conn, "t", "extra")

    assert migrations.upgrade(engine, False, [rename, drop]) == 2
    assert order == [1, 2]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id, new FROM t")).one() == (1, "x")
        assert not migrations.has_column(conn, "t", "old")
        assert not migrations.has_column(conn, "t", "extra")
    assert (settings.data_dir / "pinakes.db.v0.bak").exists()


def test_backup_keeps_old_data(engine):
    seed(settings.data_dir / "pinakes.db", ["CREATE TABLE t (id INTEGER, old TEXT)"])
    migrations.upgrade(
        engine, False, [lambda c: migrations.drop_column(c, "t", "old")]
    )
    bak = sqlite3.connect(settings.data_dir / "pinakes.db.v0.bak")
    cols = [r[1] for r in bak.execute("PRAGMA table_info(t)")]
    bak.close()
    assert "old" in cols


def test_rerun_is_noop(engine):
    calls = []
    steps = [lambda c: calls.append(1)]
    seed(settings.data_dir / "pinakes.db", ["CREATE TABLE t (id INTEGER)"])
    migrations.upgrade(engine, False, steps)
    migrations.upgrade(engine, False, steps)
    assert calls == [1]


def test_failed_step_rolls_back(engine):
    seed(settings.data_dir / "pinakes.db", ["CREATE TABLE t (id INTEGER, old TEXT)"])

    def good(conn):
        migrations.rename_column(conn, "t", "old", "new")

    def bad(conn):
        conn.execute(text("ALTER TABLE t ADD COLUMN half TEXT"))
        raise ValueError("boom")

    with pytest.raises(migrations.MigrationError, match="版本 2"):
        migrations.upgrade(engine, False, [good, bad])
    assert version(engine) == 1
    with engine.connect() as conn:
        assert migrations.has_column(conn, "t", "new")
        assert not migrations.has_column(conn, "t", "half")


def test_newer_db_refused(engine):
    migrations.upgrade(engine, True, [lambda c: None, lambda c: None])
    with pytest.raises(migrations.MigrationError, match="比程式支援的"):
        migrations.upgrade(engine, False, [lambda c: None])


def test_helpers_skip_missing(engine):
    seed(settings.data_dir / "pinakes.db", ["CREATE TABLE t (id INTEGER)"])
    with engine.begin() as conn:
        migrations.rename_column(conn, "t", "nope", "x")
        migrations.drop_column(conn, "t", "nope")
        migrations.drop_column(conn, "missing", "x")
