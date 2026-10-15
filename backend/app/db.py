from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.services.categories import seed_categories


@lru_cache
def get_engine() -> Engine:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{settings.data_dir / 'pinakes.db'}"
    return create_engine(url, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())
    with Session(get_engine()) as session:
        seed_categories(session)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
