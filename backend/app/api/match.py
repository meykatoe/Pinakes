from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import matcher, naming, pipeline, settings_store
from app.services.ai import AiClient
from app.services.tmdb import TmdbClient, TmdbError

router = APIRouter()


def tmdb_client(session: Session = Depends(get_session)) -> TmdbClient:
    try:
        return TmdbClient(
            settings_store.get_value(session, "tmdb_api_key"),
            settings_store.get_value(session, "tmdb_language"),
            session,
        )
    except TmdbError as exc:
        raise HTTPException(400, str(exc)) from exc


def ai_client(session: Session = Depends(get_session)) -> AiClient | None:
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


class MatchIn(BaseModel):
    path: str
    # 手動指定結果
    tmdb_id: int | None = None


class MatchOut(BaseModel):
    parsed: dict
    candidates: list[matcher.Candidate]
    chosen: matcher.Candidate | None
    confident: bool
    method: str | None
    reason: str = ""
    target: str | None
    error: str | None = None


@router.post("/match/preview")
async def match_preview(
    body: MatchIn,
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
    ai: AiClient | None = Depends(ai_client),
) -> MatchOut:
    parts = [p for p in body.path.replace("\\", "/").split("/") if p]
    if not parts:
        raise HTTPException(422, "路徑不可為空")
    parsed = pipeline.parse_file(session, parts)
    try:
        if body.tmdb_id is not None:
            detail = await client.details(parsed.media_type, body.tmdb_id)
            chosen = matcher.to_candidate(parsed.media_type, detail)
            res = matcher.Resolution([chosen], chosen, "manual")
        else:
            res = await matcher.resolve(client, ai, parsed, parts[-1])
            chosen = res.chosen
        values = await matcher.build_values(client, parsed, chosen)
    except TmdbError as exc:
        raise HTTPException(502, str(exc)) from exc

    key = "tv_template" if parsed.media_type == "tv" else "movie_template"
    template = settings_store.get_value(session, key)
    target, error = None, None
    if chosen is not None:
        try:
            target = naming.render(template, values, parsed.ext)
        except ValueError as exc:
            error = str(exc)
    data = {k: v for k, v in parsed.__dict__.items() if k != "rule"}
    return MatchOut(
        parsed=data,
        candidates=res.candidates,
        chosen=chosen,
        confident=chosen is not None,
        method=res.method,
        reason=res.reason,
        target=target,
        error=error,
    )
