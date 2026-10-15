from sqlmodel import Session

from app.models import Setting
from app.security import decrypt, encrypt

SECRET_KEYS = {"tmdb_api_key", "openai_api_key", "smtp_password", "stream_token"}

DEFAULTS = {
    "tmdb_api_key": "",
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "tmdb_language": "zh-TW",
    "stream_token": "",
    "ffmpeg_path": "",
    "public_base_url": "",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_security": "starttls",
    "smtp_from": "",
    "notify_to": "",
    "notify_enabled": "false",
    "watch_enabled": "false",
    "watch_interval": "30",
    "stable_seconds": "60",
    "auto_execute": "true",
    "organize_mode": "hardlink",
    "conflict_policy": "skip",
    "ai_auto_apply": "true",
    "ai_enabled": "true",
    "ai_daily_limit": "200",
    "movie_template": "{title} ({year})/{title} ({year})",
    "tv_template": "{title} ({year})/Season {season:02}/{title} - S{season:02}E{episode:02}",
    "inbox_path": "",
    "library_path": "",
    "auth_password": "",
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
