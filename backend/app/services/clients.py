from sqlmodel import Session

from app.services import settings_store
from app.services.ai import AiClient
from app.services.tmdb import TmdbClient


def build_tmdb(session: Session) -> TmdbClient:
    return TmdbClient(
        settings_store.get_value(session, "tmdb_api_key"),
        settings_store.get_value(session, "tmdb_language"),
        session,
    )


def build_ai(session: Session) -> AiClient | None:
    key = settings_store.get_value(session, "openai_api_key")
    if not key or settings_store.get_value(session, "ai_enabled") != "true":
        return None
    try:
        limit = int(settings_store.get_value(session, "ai_daily_limit"))
    except ValueError:
        limit = 200
    return AiClient(
        key,
        settings_store.get_value(session, "openai_base_url"),
        settings_store.get_value(session, "openai_model"),
        session,
        limit,
    )
