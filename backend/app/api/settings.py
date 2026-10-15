import os
import re
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from app.db import get_session
from app.services import connectivity, mailer, settings_store

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
    watch_enabled: bool
    watch_interval: int
    stable_seconds: int
    auto_execute: bool
    organize_mode: str
    conflict_policy: str
    public_base_url: str
    ffmpeg_path: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_security: str
    smtp_from: str
    notify_to: str
    notify_enabled: bool


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
    watch_enabled: bool | None = None
    watch_interval: int | None = Field(default=None, ge=5)
    stable_seconds: int | None = Field(default=None, ge=0)
    auto_execute: bool | None = None
    organize_mode: Literal["hardlink", "move", "copy", "symlink"] | None = None
    conflict_policy: Literal["skip", "overwrite", "keep_larger"] | None = None
    public_base_url: str | None = None
    ffmpeg_path: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_from: str | None = None
    notify_to: str | None = None
    notify_enabled: bool | None = None

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
    for key in ("ai_auto_apply", "watch_enabled", "auto_execute", "notify_enabled"):
        data[key] = data[key] == "true"
    for key, fallback in (
        ("ai_daily_limit", 200),
        ("watch_interval", 30),
        ("stable_seconds", 60),
        ("smtp_port", 587),
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
    for key, value in body.model_dump(exclude_none=True).items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        settings_store.set_value(session, key, str(value).strip())
    return _build_out(session)


@router.post("/test/{target}")
async def test_connection(
    target: Literal["tmdb", "openai", "smtp"], session: Session = Depends(get_session)
) -> TestResult:
    if target == "smtp":
        ok, message = await mailer.send_test(session)
    elif target == "tmdb":
        key = settings_store.get_value(session, "tmdb_api_key")
        ok, message = await connectivity.check_tmdb(key)
    else:
        key = settings_store.get_value(session, "openai_api_key")
        base = settings_store.get_value(session, "openai_base_url")
        ok, message = await connectivity.check_openai(key, base)
    return TestResult(ok=ok, message=message)
