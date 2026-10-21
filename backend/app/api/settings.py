import os
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.db import get_session
from app.services import chat_notify, cloud_move, connectivity, mailer, settings_store

router = APIRouter(prefix="/settings")

BASE_URL = re.compile(r"^https?://[^\s/?#]+$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SettingsOut(BaseModel):
    tmdb_api_key: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    tmdb_language: str
    ai_enabled: bool
    ai_daily_limit: int
    ai_auto_apply: bool
    nfo_enabled: bool
    nfo_images: bool
    watch_enabled: bool
    watch_interval: int
    stable_seconds: int
    auto_execute: bool
    organize_mode: str
    conflict_policy: str
    public_base_url: str
    ffmpeg_path: str
    hwaccel: str
    precache_enabled: bool
    precache_max_gb: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_security: str
    smtp_from: str
    notify_to: str
    notify_enabled: bool
    telegram_enabled: bool
    telegram_token: str
    telegram_chat_id: str
    discord_enabled: bool
    discord_webhook: str
    sync_enabled: bool
    sync_source_path: str
    sync_interval: int
    sync_auto_organize: bool
    sync_rc_url: str
    sync_rc_user: str
    sync_rc_pass: str
    cloud_move_enabled: bool
    cloud_source_fs: str
    cloud_library_fs: str


class SettingsIn(BaseModel):
    # None 代表不修改
    tmdb_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    tmdb_language: str | None = None
    ai_enabled: bool | None = None
    ai_daily_limit: int | None = Field(default=None, ge=0)
    ai_auto_apply: bool | None = None
    nfo_enabled: bool | None = None
    nfo_images: bool | None = None
    watch_enabled: bool | None = None
    watch_interval: int | None = Field(default=None, ge=5)
    stable_seconds: int | None = Field(default=None, ge=0)
    auto_execute: bool | None = None
    organize_mode: Literal["hardlink", "move", "copy", "symlink"] | None = None
    conflict_policy: Literal["skip", "overwrite", "keep_larger"] | None = None
    public_base_url: str | None = None
    ffmpeg_path: str | None = None
    hwaccel: Literal["auto", "off", "nvenc", "vaapi", "qsv"] | None = None
    precache_enabled: bool | None = None
    precache_max_gb: int | None = Field(default=None, ge=1)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_from: str | None = None
    notify_to: str | None = None
    notify_enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    discord_enabled: bool | None = None
    discord_webhook: str | None = None
    sync_enabled: bool | None = None
    sync_source_path: str | None = None
    sync_interval: int | None = Field(default=None, ge=1)
    sync_auto_organize: bool | None = None
    sync_rc_url: str | None = None
    sync_rc_user: str | None = None
    sync_rc_pass: str | None = None
    cloud_move_enabled: bool | None = None
    cloud_source_fs: str | None = None
    cloud_library_fs: str | None = None

    @field_validator("public_base_url")
    @classmethod
    def _base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().rstrip("/")
        if value and not BASE_URL.match(value):
            raise ValueError("網址必須是 http:// 或 https:// 開頭")
        return value

    @field_validator("ffmpeg_path")
    @classmethod
    def _ffmpeg(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if value and not (os.path.isfile(value) and os.access(value, os.X_OK)):
            raise ValueError("找不到可執行的 ffmpeg")
        return value

    @field_validator("sync_source_path")
    @classmethod
    def _source(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if value and not os.path.isdir(value):
            raise ValueError("找不到同步來源資料夾")
        return value

    @field_validator("sync_rc_url")
    @classmethod
    def _rc_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().rstrip("/")
        if value and not BASE_URL.match(value):
            raise ValueError("網址必須是 http:// 或 https:// 開頭")
        return value

    @field_validator("cloud_source_fs", "cloud_library_fs")
    @classmethod
    def _cloud_fs(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = cloud_move.normalize_fs(value)
        if value and not cloud_move.FS.match(value):
            raise ValueError("格式應為「遠端名稱:路徑」，例如 pikpak:/Media")
        return value

    @field_validator("discord_webhook")
    @classmethod
    def _webhook(cls, value: str | None) -> str | None:
        if value and not chat_notify.WEBHOOK.match(value.strip()):
            raise ValueError("Discord Webhook 網址格式錯誤")
        return value

    @field_validator("smtp_from", "notify_to")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        if value and not EMAIL.match(value.strip()):
            raise ValueError("Email 格式錯誤")
        return value


class TestResult(BaseModel):
    ok: bool
    message: str


def _mask(value: str) -> str:
    if not value:
        return ""
    return "****" + value[-4:]


def _build_out(session: Session) -> SettingsOut:
    all_data = settings_store.get_all(session)
    data = {k: all_data[k] for k in SettingsOut.model_fields}
    for key in settings_store.SECRET_KEYS & data.keys():
        data[key] = _mask(data[key])
    data["ai_enabled"] = data["ai_enabled"] == "true"
    for key in ("ai_auto_apply", "nfo_enabled", "nfo_images", "watch_enabled", "auto_execute",
                "notify_enabled", "telegram_enabled", "discord_enabled",
                "sync_enabled", "sync_auto_organize", "precache_enabled",
                "cloud_move_enabled"):
        data[key] = data[key] == "true"
    for key, fallback in (
        ("ai_daily_limit", 200),
        ("watch_interval", 30),
        ("sync_interval", 30),
        ("stable_seconds", 60),
        ("smtp_port", 587),
        ("precache_max_gb", 50),
    ):
        try:
            data[key] = int(data[key])
        except ValueError:
            data[key] = fallback
    return SettingsOut(**data)


@router.get("")
def read_settings(session: Session = Depends(get_session)) -> SettingsOut:
    return _build_out(session)


@router.put("")
def update_settings(
    body: SettingsIn, session: Session = Depends(get_session)
) -> SettingsOut:
    changes = body.model_dump(exclude_none=True)
    source = changes.get("cloud_source_fs", settings_store.get_value(session, "cloud_source_fs"))
    target = changes.get("cloud_library_fs", settings_store.get_value(session, "cloud_library_fs"))
    if source and target and cloud_move.overlaps(source, target):
        raise HTTPException(422, "雲端媒體庫不可與雲端來源互相包含")
    for key, value in changes.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        settings_store.set_value(session, key, str(value).strip())
    return _build_out(session)


@router.post("/test/{target}")
async def test_connection(
    target: Literal["tmdb", "openai", "smtp", "telegram", "discord"], session: Session = Depends(get_session)
) -> TestResult:
    if target == "smtp":
        ok, message = await mailer.send_test(session)
    elif target in ("telegram", "discord"):
        ok, message = await chat_notify.send_test(session, target)
    elif target == "tmdb":
        key = settings_store.get_value(session, "tmdb_api_key")
        ok, message = await connectivity.check_tmdb(key)
    else:
        key = settings_store.get_value(session, "openai_api_key")
        base = settings_store.get_value(session, "openai_base_url")
        ok, message = await connectivity.check_openai(key, base)
    return TestResult(ok=ok, message=message)
