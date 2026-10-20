import pytest

from app.services.naming import render, validate_template
from app.services.parser import ParsedMedia
from app.services.rules import apply_rules, validate_pattern


def test_render_movie():
    out = render("{title} ({year})/{title} ({year})", {"title": "A:B", "year": 2020}, ".mkv")
    assert out == "A B (2020)/A B (2020).mkv"


def test_render_tv_padding():
    tpl = "{title}/Season {season:02}/{title} - S{season:02}E{episode:02}"
    out = render(tpl, {"title": "Show", "season": 1, "episode": 3}, ".mkv")
    assert out == "Show/Season 01/Show - S01E03.mkv"


def test_missing_year_cleans_brackets():
    out = render("{title} ({year})", {"title": "Film", "year": None})
    assert out == "Film"


@pytest.mark.parametrize(
    "tpl",
    ["{title.__class__}", "{unknown}", "/abs/{title}", "{title!r}", "x", "{title}/../a"],
)
def test_bad_templates(tpl):
    with pytest.raises(ValueError):
        validate_template(tpl)


class R:
    def __init__(self, pattern, name="r", media_type=None):
        self.pattern, self.name, self.media_type = pattern, name, media_type


def test_pattern_validation():
    validate_pattern(r"(?P<title>.+) - (?P<episode>\d+)")
    for bad in ["(", r"\d+", r"(?P<foo>\d+)"]:
        with pytest.raises(ValueError):
            validate_pattern(bad)


def test_apply_rule_overrides():
    rule = R(r"^(?P<title>.+?) EP(?P<episode>\d+)", "ep", "tv")
    out = apply_rules([rule], "My_Show EP12", ParsedMedia())
    assert (out.title, out.episode, out.media_type, out.rule) == ("My Show", 12, "tv", "ep")


def test_no_rule_match_keeps_parsed():
    parsed = ParsedMedia(title="X")
    out = apply_rules([R(r"(?P<title>ZZZ)")], "abc", parsed)
    assert out.title == "X" and out.rule is None
