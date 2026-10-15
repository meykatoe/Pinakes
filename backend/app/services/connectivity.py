import httpx

TMDB_BASE = "https://api.themoviedb.org/3"


async def check_tmdb(
    api_key: str, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[bool, str]:
    if not api_key:
        return False, "尚未設定金鑰"
    headers, params = {}, {}
    # v4 令牌較長
    if len(api_key) > 40:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        params["api_key"] = api_key
    async with httpx.AsyncClient(transport=transport, timeout=10) as client:
        try:
            res = await client.get(
                f"{TMDB_BASE}/configuration", headers=headers, params=params
            )
        except httpx.HTTPError as exc:
            return False, f"連線失敗：{exc.__class__.__name__}"
    if res.status_code == 200:
        return True, "連線成功"
    return False, f"驗證失敗（HTTP {res.status_code}）"


async def check_openai(
    api_key: str,
    base_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bool, str]:
    if not api_key:
        return False, "尚未設定金鑰"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(transport=transport, timeout=10) as client:
        try:
            res = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        except httpx.HTTPError as exc:
            return False, f"連線失敗：{exc.__class__.__name__}"
    if res.status_code == 200:
        return True, "連線成功"
    return False, f"驗證失敗（HTTP {res.status_code}）"
