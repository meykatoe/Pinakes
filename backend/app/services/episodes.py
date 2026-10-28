from datetime import date

from app.services.tmdb import TmdbClient


def _aired(episode: dict, today: date) -> bool:
    try:
        return date.fromisoformat(episode.get("air_date") or "") <= today
    except ValueError:
        return False


async def find_missing(
    client: TmdbClient, tmdb_id: int, owned: set[tuple[int, int]], today: date
) -> list[dict]:
    have: dict[int, set[int]] = {}
    for season, episode in owned:
        have.setdefault(season, set()).add(episode)
    gaps = []
    for season in sorted(have):
        # 跳過特別篇
        if season == 0:
            continue
        data = await client.season(tmdb_id, season)
        aired = [e for e in data.get("episodes", []) if _aired(e, today)]
        numbers = {e["episode_number"] for e in aired}
        missing = [
            {
                "episode": e["episode_number"],
                "name": e.get("name") or "",
                "air_date": e["air_date"],
            }
            for e in aired
            if e["episode_number"] not in have[season]
        ]
        gaps.append(
            {
                "season": season,
                "aired": len(numbers),
                "owned": len(numbers & have[season]),
                "missing": sorted(missing, key=lambda m: m["episode"]),
            }
        )
    return gaps
