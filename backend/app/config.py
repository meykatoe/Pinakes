import os
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def default_data_dir() -> Path:
    """沿用目前目錄下的舊資料，否則用各平台的使用者資料夾。"""
    legacy = Path("data")
    if (legacy / "pinakes.db").exists():
        return legacy
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "pinakes"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PINAKES_", env_file=".env")

    # 資料目錄
    data_dir: Path = Field(default_factory=default_data_dir)
    # 背景監控
    watch_loop: bool = True
    # 前端來源
    cors_origins: list[str] = ["http://localhost:5173"]
    # 前端檔案
    static_dir: Path = DIST


settings = Settings()
