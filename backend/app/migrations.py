import sqlite3
from collections.abc import Callable

from sqlalchemy import Connection, Engine, inspect, text

from app.config import settings

TABLE = "schema_version"

Migration = Callable[[Connection], None]

# 依序執行，只能往後新增
MIGRATIONS: list[Migration] = []


class MigrationError(RuntimeError):
    pass


def has_column(conn: Connection, table: str, column: str) -> bool:
    insp = inspect(conn)
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def rename_column(conn: Connection, table: str, old: str, new: str) -> None:
    if has_column(conn, table, old) and not has_column(conn, table, new):
        conn.execute(text(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"'))


def drop_column(conn: Connection, table: str, column: str) -> None:
    if has_column(conn, table, column):
        conn.execute(text(f'ALTER TABLE "{table}" DROP COLUMN "{column}"'))


def _read(conn: Connection) -> int | None:
    row = conn.execute(text(f"SELECT version FROM {TABLE}")).first()
    return row[0] if row else None


def _backup(engine: Engine, version: int) -> None:
    path = settings.data_dir / f"pinakes.db.v{version}.bak"
    src = engine.raw_connection()
    try:
        dst = sqlite3.connect(path)
        try:
            src.driver_connection.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def current_version(engine: Engine) -> int | None:
    with engine.connect() as conn:
        if not inspect(conn).has_table(TABLE):
            return None
        return _read(conn)


def upgrade(
    engine: Engine, fresh: bool, migrations: list[Migration] | None = None
) -> int:
    steps = MIGRATIONS if migrations is None else migrations
    latest = len(steps)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE IF NOT EXISTS {TABLE} (version INTEGER NOT NULL)"))
        current = _read(conn)
        if current is None:
            # 全新庫直接標最新
            current = latest if fresh else 0
            conn.execute(text(f"INSERT INTO {TABLE} (version) VALUES (:v)"), {"v": current})
    if current > latest:
        raise MigrationError(
            f"資料庫版本 {current} 比程式支援的 {latest} 新，請升級 Pinakes 後再啟動"
        )
    if current == latest:
        return current
    _backup(engine, current)
    for n in range(current, latest):
        try:
            with engine.begin() as conn:
                # sqlite3 的 DDL 不會自動開交易
                conn.exec_driver_sql("BEGIN")
                steps[n](conn)
                conn.execute(text(f"UPDATE {TABLE} SET version = :v"), {"v": n + 1})
        except Exception as exc:
            raise MigrationError(f"遷移到版本 {n + 1} 失敗：{exc}") from exc
    return latest
