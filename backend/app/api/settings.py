from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
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


class SettingsIn(BaseModel):
    # None 代表不修改
    tmdb_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    tmdb_language: str | None = None


class TestResult(BaseModel):
    ok: bool
    message: str


def _mask(value: str) -> str:
    if not value:
        return ""
    return "****" + value[-4:]


def _build_out(session: Session) -> SettingsOut:
    data = settings_store.get_all(session)
    for key in settings_store.SECRET_KEYS:
        data[key] = _mask(data[key])
    return SettingsOut(**data)


@router.get("")
def read_settings(session: Session = Depends(get_session)) -> SettingsOut:
    return _build_out(session)


@router.put("")
def update_settings(
    body: SettingsIn, session: Session = Depends(get_session)
) -> SettingsOut:
    for key, value in body.model_dump(exclude_none=True).items():
        settings_store.set_value(session, key, value.strip())
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
