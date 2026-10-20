from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    # movie 或 tv
    media_type: str
    # 相對於已整理目錄
    subdir: str = Field(unique=True)
    builtin: bool = False


class ParseRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    pattern: str
    # 數字越小越先比對
    priority: int = 100
    enabled: bool = True
    media_type: str | None = None


class TmdbCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    payload: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AiCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    payload: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AiUsage(SQLModel, table=True):
    day: str = Field(primary_key=True)
    calls: int = 0


class MediaItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_path: str = Field(index=True)
    size: int = 0
    mtime: int = 0
    # pending_review planned done failed skipped undone
    status: str = Field(default="pending_review", index=True)
    media_type: str = "movie"
    tmdb_id: int | None = None
    title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    category_id: int | None = None
    target_path: str = ""
    mode: str = ""
    method: str | None = None
    reason: str = ""
    error: str = ""
    candidates: str = "[]"
    companions: str = "[]"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OperationLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(index=True)
    action: str
    src: str
    dst: str
    backup: str = ""
    undone: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MediaMeta(SQLModel, table=True):
    media_type: str = Field(primary_key=True)
    tmdb_id: int = Field(primary_key=True)
    title: str = ""
    original_title: str = ""
    year: int | None = None
    overview: str = ""
    tagline: str = ""
    genres: str = "[]"
    rating: float = 0.0
    runtime: int | None = None
    seasons: int | None = None
    imdb_id: str = ""
    credits: str = "[]"
    trailer_key: str = ""
    poster_path: str | None = None
    backdrop_path: str | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlayerProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # link 或 m3u
    kind: str = "link"
    template: str = ""
    enabled: bool = True


class SyncedFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # 相對於掛載來源目錄
    rel_path: str = Field(index=True)
    size: int = 0
    mtime: int = 0
    dest_path: str = ""
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SyncFailure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    rel_path: str = Field(index=True)
    size: int = 0
    mtime: int = 0
    error: str = ""
    noticed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
