import json
from xml.etree import ElementTree as ET

from app.models import MediaMeta
from app.services import nfo, scraper


def make_meta(**kw) -> MediaMeta:
    base = dict(
        media_type="movie", tmdb_id=7, title="A & B <1>", original_title="Orig",
        year=2020, overview="Plot", genres=json.dumps(["Drama", "Action"]),
        rating=7.5, runtime=120, imdb_id="tt123",
        credits=json.dumps([{"name": "Ann", "character": "Bob"}]),
        trailer_key="abc",
    )
    base.update(kw)
    return MediaMeta(**base)


def test_movie_fields():
    root = ET.fromstring(nfo.movie_nfo(make_meta()))
    assert root.tag == "movie"
    assert root.findtext("title") == "A & B <1>"
    assert root.findtext("year") == "2020"
    assert [g.text for g in root.findall("genre")] == ["Drama", "Action"]
    assert root.findtext("actor/name") == "Ann"
    assert root.findtext("actor/role") == "Bob"
    assert root.findtext("trailer").endswith("watch?v=abc")


def test_unique_ids():
    root = ET.fromstring(nfo.movie_nfo(make_meta()))
    ids = {u.get("type"): u.text for u in root.findall("uniqueid")}
    assert ids == {"tmdb": "7", "imdb": "tt123"}
    assert root.find("uniqueid[@type='tmdb']").get("default") == "true"


def test_skip_empty_fields():
    meta = make_meta(imdb_id="", tagline="", runtime=None, rating=0.0,
                     credits="[]", trailer_key="")
    root = ET.fromstring(nfo.movie_nfo(meta))
    for tag in ("tagline", "runtime", "rating", "actor", "trailer", "imdbid"):
        assert root.find(tag) is None
    assert [u.get("type") for u in root.findall("uniqueid")] == ["tmdb"]


def test_escape_and_header():
    text = nfo.movie_nfo(make_meta())
    assert text.startswith('<?xml version="1.0"')
    assert "A &amp; B &lt;1&gt;" in text


def test_tvshow_root():
    root = ET.fromstring(nfo.tvshow_nfo(make_meta(media_type="tv")))
    assert root.tag == "tvshow"


def test_episode():
    ep = {"name": "Pilot", "season_number": 1, "episode_number": 2,
          "air_date": "2020-01-02", "overview": "Hi", "id": 99,
          "vote_average": 8.26}
    root = ET.fromstring(nfo.episode_nfo(make_meta(title="Show"), ep))
    assert root.tag == "episodedetails"
    assert root.findtext("showtitle") == "Show"
    assert root.findtext("season") == "1"
    assert root.findtext("aired") == "2020-01-02"
    assert root.findtext("rating") == "8.3"
    assert root.findtext("uniqueid") == "99"


def test_build_meta_imdb():
    movie = scraper.build_meta("movie", {"id": 1, "imdb_id": "tt1"})
    assert movie.imdb_id == "tt1"
    tv = scraper.build_meta("tv", {"id": 2, "external_ids": {"imdb_id": "tt2"}})
    assert tv.imdb_id == "tt2"
    assert scraper.build_meta("tv", {"id": 3}).imdb_id == ""
