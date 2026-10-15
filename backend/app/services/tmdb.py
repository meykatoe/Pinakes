import json
from datetime import UTC, datetime, timedelta

import httpx
from sqlmodel import Session

from app.models import TmdbCache

BASE = "https://api.themoviedb.org/3"
CACHE_TTL = timedelta(days=7)


class TmdbError(Exception):
    pass


def auth(api_key: str) -> tuple[dict, dict]:
    # v4 令牌較長
    if len(api_key) > 40:
        return {"Authorization": f"Bearer {api_key}"}, {}
    return {}, {"api_key": api_key}


class TmdbClient:
    def __init__(
        self,
        api_key: str,
        language: str = "zh-TW",
        session: Session | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise TmdbError("尚未設定 TMDB 金鑰")
        self.language = language
        self.session = session
        self.transport = transport
        self.headers, self.auth_params = auth(api_key)

    def _cache_key(self, path: str, params: dict) -> str:
        return path + "?" + json.dumps(params, sort_keys=True, ensure_ascii=False)

    def _cache_get(self, key: str) -> dict | None:
        if self.session is None:
            return None
        row = self.session.get(TmdbCache, key)
        if row is None:
            return None
        fetched = row.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        if datetime.now(UTC) - fetched > CACHE_TTL:
            return None
        return json.loads(row.payload)

    def _cache_put(self, key: str, data: dict) -> None:
        if self.session is None:
            return
        self.session.merge(TmdbCache(key=key, payload=json.dumps(data)))
        self.session.commit()

    async def get(self, path: str, **params) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        params["language"] = self.language
        key = self._cache_key(path, params)
        if (cached := self._cache_get(key)) is not None:
            return cached
        async with httpx.AsyncClient(transport=self.transport, timeout=15) as client:
            try:
                res = await client.get(
                    BASE + path,
                    headers=self.headers,
                    params={**params, **self.auth_params},
                )
            except httpx.HTTPError as exc:
                raise TmdbError(f"連線失敗：{exc.__class__.__name__}") from exc
        if res.status_code == 404:
            raise TmdbError("TMDB 找不到資料")
        if res.status_code != 200:
            raise TmdbError(f"TMDB 回應錯誤（HTTP {res.status_code}）")
        data = res.json()
        self._cache_put(key, data)
        return data

    async def search(self, media_type: str, query: str, year: int | None) -> list[dict]:
        if media_type == "tv":
            data = await self.get("/search/tv", query=query, first_air_date_year=year)
        else:
            data = await self.get(
                "/search/movie", query=query, year=year, include_adult="false"
            )
        return data.get("results", [])

    async def details(self, media_type: str, tmdb_id: int) -> dict:
        return await self.get(f"/{'tv' if media_type == 'tv' else 'movie'}/{tmdb_id}")

    async def episode(self, tv_id: int, season: int, episode: int) -> dict:
        return await self.get(f"/tv/{tv_id}/season/{season}/episode/{episode}")
