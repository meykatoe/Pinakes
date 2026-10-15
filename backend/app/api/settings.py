from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db import get_session
from app.services import connectivity, settings_store

router = APIRouter(prefix="/settings")


class SettingsOut(BaseModel):
    tmdb_api_key: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    tmdb_language: str
    ai_enabled: bool
    ai_daily_limit: int


class SettingsIn(BaseModel):
    # None 代表不修改
    tmdb_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    tmdb_language: str | None = None
    ai_enabled: bool | None = None
    ai_daily_limit: int | None = Field(default=None, ge=0)


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
    for key in settings_store.SECRET_KEYS:
        data[key] = _mask(data[key])
    data["ai_enabled"] = data["ai_enabled"] == "true"
    try:
        data["ai_daily_limit"] = int(data["ai_daily_limit"])
    except ValueError:
        data["ai_daily_limit"] = 200
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
    target: Literal["tmdb", "openai"], session: Session = Depends(get_session)
) -> TestResult:
    if target == "tmdb":
        key = settings_store.get_value(session, "tmdb_api_key")
        ok, message = await connectivity.check_tmdb(key)
    else:
        key = settings_store.get_value(session, "openai_api_key")
        base = settings_store.get_value(session, "openai_base_url")
        ok, message = await connectivity.check_openai(key, base)
    return TestResult(ok=ok, message=message)
