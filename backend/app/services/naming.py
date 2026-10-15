import re
from pathlib import PurePosixPath
from string import Formatter

FIELDS = {
    "title", "original_title", "year", "season", "episode", "episode_title",
    "resolution", "source", "codec", "group", "tmdb_id",
}

SAMPLE = {
    "title": "Sample", "original_title": "Sample", "year": 2020, "season": 1,
    "episode": 2, "episode_title": "Pilot", "resolution": "1080p",
    "source": "WEB-DL", "codec": "x264", "group": "GRP", "tmdb_id": 1,
}

_ILLEGAL = re.compile(r'[<>:"\\|?*\x00-\x1f]')


def _clean_part(part: str) -> str:
    part = _ILLEGAL.sub(" ", part)
    part = re.sub(r"\(\s*\)|\[\s*\]", "", part)
    part = re.sub(r"\s+", " ", part)
    part = re.sub(r"(?:\s*-\s*)+$", "", part)
    return part.strip(" .")


def render(template: str, values: dict, ext: str = "") -> str:
    out = []
    for literal, field_name, spec, conv in Formatter().parse(template):
        out.append(literal)
        if field_name is None:
            continue
        if conv or field_name not in FIELDS:
            raise ValueError(f"不支援的欄位：{field_name}")
        value = values.get(field_name)
        if value in (None, ""):
            continue
        try:
            out.append(format(value, spec))
        except ValueError as exc:
            raise ValueError(f"格式錯誤：{field_name}:{spec}") from exc
    raw = "".join(out).split("/")
    if ".." in (p.strip() for p in raw):
        raise ValueError("樣板結果無效")
    parts = [_clean_part(p) for p in raw]
    parts = [p for p in parts if p]
    if not parts or ".." in parts:
        raise ValueError("樣板結果無效")
    parts[-1] += ext
    return str(PurePosixPath(*parts))


def validate_template(template: str) -> None:
    if template.startswith("/") or "\\" in template:
        raise ValueError("樣板必須是相對路徑，並使用 / 分隔")
    if "{title}" not in template:
        raise ValueError("樣板必須包含 {title}")
    render(template, SAMPLE)
