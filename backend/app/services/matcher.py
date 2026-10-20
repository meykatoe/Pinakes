import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.services.parser import ParsedMedia
from app.services.tmdb import TmdbClient, TmdbError

CONFIDENT_SCORE = 0.9
CONFIDENT_MARGIN = 0.1
AI_MIN_CONFIDENCE = 0.7

if TYPE_CHECKING:
    from app.services.ai import AiClient


class Candidate(BaseModel):
    tmdb_id: int
    media_type: str
    title: str
    original_title: str
    year: int | None
    overview: str = ""
    poster_path: str | None = None
    popularity: float = 0.0
    score: float = 0.0


def _year(date: str | None) -> int | None:
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def to_candidate(media_type: str, item: dict) -> Candidate:
    if media_type == "tv":
        title, original = item.get("name", ""), item.get("original_name", "")
        year = _year(item.get("first_air_date"))
    else:
        title, original = item.get("title", ""), item.get("original_title", "")
        year = _year(item.get("release_date"))
    return Candidate(
        tmdb_id=item["id"],
        media_type=media_type,
        title=title,
        original_title=original,
        year=year,
        overview=item.get("overview") or "",
        poster_path=item.get("poster_path"),
        popularity=item.get("popularity") or 0.0,
    )


def _norm(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def score(parsed: ParsedMedia, cand: Candidate) -> float:
    query = _norm(parsed.title)
    ratios = [
        SequenceMatcher(None, query, _norm(name)).ratio()
        for name in (cand.title, cand.original_title)
        if name
    ]
    value = max(ratios, default=0.0)
    if parsed.year and cand.year:
        diff = abs(parsed.year - cand.year)
        value += 0.15 if diff == 0 else 0.05 if diff == 1 else -0.2
    return round(max(0.0, min(1.0, value)), 4)


async def find_candidates(client: TmdbClient, parsed: ParsedMedia) -> list[Candidate]:
    if not parsed.title:
        return []
    results = await client.search(parsed.media_type, parsed.title, parsed.year)
    if not results and parsed.year:
        results = await client.search(parsed.media_type, parsed.title, None)
    cands = [to_candidate(parsed.media_type, r) for r in results]
    for c in cands:
        c.score = score(parsed, c)
    cands.sort(key=lambda c: (c.score, c.popularity), reverse=True)
    return cands[:10]


def decide(cands: list[Candidate]) -> Candidate | None:
    if not cands or cands[0].score < CONFIDENT_SCORE:
        return None
    if len(cands) > 1 and cands[0].score - cands[1].score < CONFIDENT_MARGIN:
        return None
    return cands[0]


async def build_values(
    client: TmdbClient, parsed: ParsedMedia, chosen: Candidate | None
) -> dict:
    values = {**parsed.__dict__, "original_title": parsed.title}
    if chosen is None:
        return values
    values.update(
        title=chosen.title or parsed.title,
        original_title=chosen.original_title or chosen.title,
        year=chosen.year,
        tmdb_id=chosen.tmdb_id,
    )
    if chosen.media_type == "tv" and parsed.season and parsed.episode:
        try:
            ep = await client.episode(chosen.tmdb_id, parsed.season, parsed.episode)
            values["episode_title"] = ep.get("name", "")
        except TmdbError:
            pass
    return values


@dataclass
class Resolution:
    candidates: list[Candidate]
    chosen: Candidate | None = None
    method: str | None = None
    reason: str = ""


async def resolve(
    client: TmdbClient,
    ai: AiClient | None,
    parsed: ParsedMedia,
    filename: str,
) -> Resolution:
    from app.services.ai import AiError

    cands = await find_candidates(client, parsed)
    chosen = decide(cands)
    if chosen is not None:
        return Resolution(cands, chosen, "rule")
    res = Resolution(cands)
    if ai is None:
        return res
    try:
        if not cands:
            rewrite = await ai.rewrite(filename)
            if rewrite.title:
                alt = replace(parsed, title=rewrite.title, year=rewrite.year or parsed.year)
                cands = await find_candidates(client, alt)
                res.candidates = cands
                if chosen := decide(cands):
                    return Resolution(cands, chosen, "ai", "AI 改寫搜尋字串後比對")
        if cands:
            choice = await ai.choose(filename, parsed, cands)
            picked = next((c for c in cands if c.tmdb_id == choice.tmdb_id), None)
            if picked and choice.confidence >= AI_MIN_CONFIDENCE:
                return Resolution(cands, picked, "ai", choice.reason)
            res.reason = choice.reason or "AI 無法確定"
    except AiError as exc:
        res.reason = f"AI 無法使用：{exc}"
    return res
