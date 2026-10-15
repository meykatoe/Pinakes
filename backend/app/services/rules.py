import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

from app.services.parser import ParsedMedia, clean_title

ALLOWED_GROUPS = {
    "title", "year", "season", "episode", "resolution", "source", "codec", "group",
}
INT_GROUPS = {"year", "season", "episode"}


class RuleLike(Protocol):
    name: str
    pattern: str
    media_type: str | None


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


def validate_pattern(pattern: str) -> None:
    try:
        compiled = _compile(pattern)
    except re.error as exc:
        raise ValueError(f"正則錯誤：{exc}") from exc
    names = set(compiled.groupindex)
    if not names:
        raise ValueError("至少需要一個命名群組")
    unknown = names - ALLOWED_GROUPS
    if unknown:
        raise ValueError(f"不支援的群組：{', '.join(sorted(unknown))}")


def apply_rules(
    rules: Sequence[RuleLike], stem: str, parsed: ParsedMedia
) -> ParsedMedia:
    text = re.sub(r"[._]+", " ", stem)
    for rule in rules:
        m = _compile(rule.pattern).search(text)
        if not m:
            continue
        for key, value in m.groupdict().items():
            if not value:
                continue
            if key in INT_GROUPS:
                if value.isdigit():
                    setattr(parsed, key, int(value))
            elif key == "title":
                parsed.title = clean_title(value)
            else:
                setattr(parsed, key, value.strip())
        if rule.media_type:
            parsed.media_type = rule.media_type
        elif parsed.season is not None or parsed.episode is not None:
            parsed.media_type = "tv"
        parsed.rule = rule.name
        break
    return parsed
