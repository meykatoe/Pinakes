import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

VIDEO_EXTS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".m2ts", ".webm",
}

_B = r"(?<![A-Za-z0-9])"
_E = r"(?![A-Za-z0-9])"

RES = re.compile(_B + r"(?P<v>(?:2160|1080|720|576|480)[pi]|4K)" + _E, re.I)
SRC = re.compile(
    _B + r"(?P<v>WEB[ -]?DL|WEB[ -]?Rip|WEB|Blu[ -]?Ray|BD[ -]?Rip|BDRemux|REMUX"
    r"|HDTV|DVD[ -]?Rip|HDRip)" + _E,
    re.I,
)
CODEC = re.compile(_B + r"(?P<v>[xh][ -]?26[45]|HEVC|AVC|AV1|XviD)" + _E, re.I)

SXE = re.compile(
    _B + r"S(?P<s>\d{1,2})[ -]?E(?P<e>\d{1,4})(?:[ -]?E\d{1,4})*(?![0-9])", re.I
)
NXN = re.compile(_B + r"(?P<s>\d{1,2})x(?P<e>\d{2,3})" + _E, re.I)
SEASON = re.compile(_B + r"(?:Season|S)[ -]?(?P<s>\d{1,2})" + _E, re.I)
CN_SEASON = re.compile(r"第\s*(?P<s>\d{1,2})\s*季")
CN_EP = re.compile(r"第\s*(?P<e>\d{1,4})\s*[集話话]")
ANIME_EP = re.compile(r"(?:^|[\s\])】])-\s*(?P<e>\d{2,3})(?:v\d)?(?=[\s\[(]|$)")
BRACKET_EP = re.compile(r"\[(?P<e>\d{2,3})\]")
YEAR = re.compile(r"(?<![0-9])(?P<y>(?:19|20)\d{2})(?![0-9])")
LEAD_GROUP = re.compile(r"^\s*[\[【](?P<g>[^\]】]+)[\]】]")
TAIL_GROUP = re.compile(r"-(?P<g>[A-Za-z0-9]{2,15})$")
SEASON_DIR = re.compile(
    r"^(?:Season|S)[ ._-]?(?P<s>\d{1,2})$|^第\s*(?P<c>\d{1,2})\s*季$", re.I
)


@dataclass
class ParsedMedia:
    title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    resolution: str = ""
    source: str = ""
    codec: str = ""
    group: str = ""
    ext: str = ""
    media_type: str = "movie"
    rule: str | None = field(default=None, compare=False)


def clean_title(text: str) -> str:
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -[]()【】")


def _first(patterns: list[re.Pattern], text: str) -> re.Match | None:
    hits = [m for p in patterns if (m := p.search(text))]
    return min(hits, key=lambda m: m.start()) if hits else None


def parse_name(stem: str) -> ParsedMedia:
    result = ParsedMedia()
    text = re.sub(r"[._]+", " ", stem)

    lead = LEAD_GROUP.match(text)
    if lead:
        result.group = lead.group("g").strip()
        text = text[lead.end() :]
    text = text.strip()

    for attr, pattern in (("resolution", RES), ("source", SRC), ("codec", CODEC)):
        if m := pattern.search(text):
            value = m.group("v")
            setattr(result, attr, re.sub(r"[ -]", "", value) if attr == "codec" else value)

    if not result.group and (result.source or result.codec):
        if m := TAIL_GROUP.search(text):
            result.group = m.group("g")

    for pattern in (SXE, NXN):
        if m := pattern.search(text):
            result.season, result.episode = int(m.group("s")), int(m.group("e"))
            break
    else:
        if m := SEASON.search(text) or CN_SEASON.search(text):
            result.season = int(m.group("s"))
        if m := CN_EP.search(text) or ANIME_EP.search(text) or BRACKET_EP.search(text):
            result.episode = int(m.group("e"))
    if result.season is None and (m := CN_SEASON.search(text)):
        result.season = int(m.group("s"))

    markers = [RES, SRC, CODEC, SXE, NXN, SEASON, CN_SEASON, CN_EP, ANIME_EP, BRACKET_EP]
    cut = _first(markers, text)
    head = text[: cut.start()] if cut else text

    years = [m for m in YEAR.finditer(head) if m.start() > 0]
    if years:
        result.year = int(years[-1].group("y"))
        head = head[: years[-1].start()]
    elif cut and (m := next((y for y in YEAR.finditer(text, cut.start())), None)):
        result.year = int(m.group("y"))

    result.title = clean_title(head)
    result.media_type = (
        "tv" if result.season is not None or result.episode is not None else "movie"
    )
    return result


def parse_path(parts: list[str]) -> ParsedMedia:
    name = PurePosixPath(parts[-1])
    ext = name.suffix.lower() if name.suffix.lower() in VIDEO_EXTS else ""
    stem = name.name[: len(name.name) - len(ext)] if ext else name.name
    result = parse_name(stem)
    result.ext = ext
    fill_from_parents(result, parts[:-1])
    return result


def fill_from_parents(result: ParsedMedia, parents: list[str]) -> None:
    for name in reversed(parents):
        m = SEASON_DIR.match(name.strip())
        if m:
            if result.season is None:
                result.season = int(m.group("s") or m.group("c"))
            continue
        if not result.title:
            result.title = parse_name(name).title
            if not result.year:
                result.year = parse_name(name).year
    finalize(result)


def finalize(result: ParsedMedia) -> None:
    if result.episode is not None and result.season is None:
        result.season = 1
    if result.season is not None or result.episode is not None:
        result.media_type = "tv"
