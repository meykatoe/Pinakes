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
