from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import DateTime, Engine, event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.services.categories import seed_categories
from app.services.player import seed_players


@lru_cache
def get_engine() -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{settings.data_dir / 'pinakes.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    event.listen(engine, "connect", _pragmas)
    return engine


def _pragmas(conn, _record) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


def _literal(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _fallback(col) -> object:
    kind = getattr(col.type, "impl", col.type)
    if isinstance(kind, DateTime) or kind is DateTime:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    try:
        kind = col.type.python_type
    except NotImplementedError:
        return ""
    return 0 if kind in (int, float, bool) else ""


def migrate(engine: Engine) -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                kind = col.type.compile(engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {kind}'
                default = None
                if col.default is not None and col.default.is_scalar:
                    default = col.default.arg
                if default is None and not col.nullable:
                    default = _fallback(col)
                if default is not None:
                    ddl += f" DEFAULT {_literal(default)}"
                conn.execute(text(ddl))


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    migrate(engine)
    with Session(engine) as session:
        seed_categories(session)
        seed_players(session)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
