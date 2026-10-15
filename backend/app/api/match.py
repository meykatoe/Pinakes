from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import matcher, naming, pipeline, settings_store
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


class MatchIn(BaseModel):
    path: str
    # 手動指定結果
    tmdb_id: int | None = None


class MatchOut(BaseModel):
    parsed: dict
    candidates: list[matcher.Candidate]
    chosen: matcher.Candidate | None
    confident: bool
    target: str | None
    error: str | None = None


@router.post("/match/preview")
async def match_preview(
    body: MatchIn,
    session: Session = Depends(get_session),
    client: TmdbClient = Depends(tmdb_client),
) -> MatchOut:
    parts = [p for p in body.path.replace("\\", "/").split("/") if p]
    if not parts:
        raise HTTPException(422, "路徑不可為空")
    parsed = pipeline.parse_file(session, parts)
    try:
        cands = await matcher.find_candidates(client, parsed)
        if body.tmdb_id is not None:
            detail = await client.details(parsed.media_type, body.tmdb_id)
            chosen = matcher.to_candidate(parsed.media_type, detail)
            confident = True
        else:
            chosen = matcher.decide(cands)
            confident = chosen is not None
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
        candidates=cands,
        chosen=chosen,
        confident=confident,
        target=target,
        error=error,
    )
