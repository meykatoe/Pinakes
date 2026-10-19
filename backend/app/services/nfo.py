import json
from xml.etree import ElementTree as ET

HEADER = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'


def _add(parent: ET.Element, tag: str, value) -> None:
    if value in (None, ""):
        return
    ET.SubElement(parent, tag).text = str(value)


def _ids(root: ET.Element, meta) -> None:
    _add(root, "tmdbid", meta.tmdb_id)
    uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
    uid.text = str(meta.tmdb_id)
    if meta.imdb_id:
        _add(root, "imdbid", meta.imdb_id)
        ET.SubElement(root, "uniqueid", type="imdb").text = meta.imdb_id


def _common(root: ET.Element, meta) -> None:
    _add(root, "title", meta.title)
    _add(root, "originaltitle", meta.original_title)
    _add(root, "year", meta.year)
    _add(root, "plot", meta.overview)
    _add(root, "tagline", meta.tagline)
    _add(root, "runtime", meta.runtime)
    if meta.rating:
        _add(root, "rating", meta.rating)
    for genre in json.loads(meta.genres or "[]"):
        _add(root, "genre", genre)
    for order, person in enumerate(json.loads(meta.credits or "[]")):
        actor = ET.SubElement(root, "actor")
        _add(actor, "name", person.get("name"))
        _add(actor, "role", person.get("character"))
        _add(actor, "order", order)
    if meta.trailer_key:
        url = f"https://www.youtube.com/watch?v={meta.trailer_key}"
        _add(root, "trailer", url)
    _ids(root, meta)


def _dump(root: ET.Element) -> str:
    ET.indent(root)
    return HEADER + ET.tostring(root, encoding="unicode") + "\n"


def movie_nfo(meta) -> str:
    root = ET.Element("movie")
    _common(root, meta)
    return _dump(root)


def tvshow_nfo(meta) -> str:
    root = ET.Element("tvshow")
    _common(root, meta)
    return _dump(root)


def episode_nfo(meta, ep: dict) -> str:
    root = ET.Element("episodedetails")
    _add(root, "title", ep.get("name"))
    _add(root, "showtitle", meta.title)
    _add(root, "season", ep.get("season_number"))
    _add(root, "episode", ep.get("episode_number"))
    _add(root, "aired", ep.get("air_date"))
    _add(root, "plot", ep.get("overview"))
    _add(root, "runtime", ep.get("runtime"))
    if ep.get("vote_average"):
        _add(root, "rating", round(float(ep["vote_average"]), 1))
    if ep.get("id"):
        uid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uid.text = str(ep["id"])
    return _dump(root)
