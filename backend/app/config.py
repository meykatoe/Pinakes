from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PINAKES_", env_file=".env")

    # 資料目錄
    data_dir: Path = Path("data")
    # 前端來源
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
