import pytest

from app.services.parser import parse_path


def p(path):
    return parse_path(path.split("/"))


def test_movie():
    r = p("The.Matrix.1999.1080p.BluRay.x264-GRP.mkv")
    assert (r.title, r.year, r.media_type) == ("The Matrix", 1999, "movie")
    assert (r.resolution, r.source, r.codec, r.group) == (
        "1080p", "BluRay", "x264", "GRP"
    )
    assert r.ext == ".mkv"


def test_year_in_title():
    r = p("Blade Runner 2049 2017 2160p WEB-DL H.265.mkv")
    assert (r.title, r.year, r.codec) == ("Blade Runner 2049", 2017, "H265")
    r = p("2012 (2009) 1080p.mkv")
    assert (r.title, r.year) == ("2012", 2009)


def test_tv_sxe():
    r = p("Breaking.Bad.S02E05.720p.HDTV.x264-CTU.mkv")
    assert (r.title, r.season, r.episode, r.media_type) == (
        "Breaking Bad", 2, 5, "tv"
    )


def test_tv_nxn():
    r = p("Show/Season 1/Show - 1x04 - Title.avi")
    assert (r.title, r.season, r.episode) == ("Show", 1, 4)


def test_anime_group_episode():
    r = p("[Sub] Some Anime - 05 [1080p][HEVC].mkv")
    assert (r.title, r.episode, r.season, r.group) == ("Some Anime", 5, 1, "Sub")


def test_chinese_markers():
    r = p("[Sub] 某動畫 第2季 第07集 [1080p].mp4")
    assert (r.title, r.season, r.episode) == ("某動畫", 2, 7)


def test_parent_fallback():
    r = p("Show Name (2019)/Season 2/S02E03.mkv")
    assert (r.title, r.year, r.season, r.episode) == ("Show Name", 2019, 2, 3)


def test_no_tech_tags():
    r = p("Inception (2010).mkv")
    assert (r.title, r.year) == ("Inception", 2010)


@pytest.mark.parametrize("name", ["readme.txt", "a"])
def test_unknown_ext_kept_in_title(name):
    assert p(name).ext == ""
