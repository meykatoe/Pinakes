from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PINAKES_", env_file=".env")

    # 資料目錄
    data_dir: Path = Path("data")
    # 背景監控
    watch_loop: bool = True
    # 前端來源
    cors_origins: list[str] = ["http://localhost:5173"]
    # 前端檔案
    static_dir: Path = DIST


settings = Settings()
