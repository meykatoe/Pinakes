from sqlmodel import Session

from app.models import Setting
from app.security import decrypt, encrypt

SECRET_KEYS = {"tmdb_api_key", "openai_api_key"}

DEFAULTS = {
    "tmdb_api_key": "",
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "tmdb_language": "zh-TW",
    "inbox_path": "",
    "library_path": "",
}


def get_value(session: Session, key: str) -> str:
    row = session.get(Setting, key)
    if row is None or row.value == "":
        return DEFAULTS[key]
    return decrypt(row.value) if key in SECRET_KEYS else row.value


def set_value(session: Session, key: str, value: str) -> None:
    stored = encrypt(value) if key in SECRET_KEYS and value else value
    session.merge(Setting(key=key, value=stored))
    session.commit()


def get_all(session: Session) -> dict[str, str]:
    return {key: get_value(session, key) for key in DEFAULTS}
