import hmac
import re
import secrets
from urllib.parse import quote

from sqlmodel import Session, select

from app.models import PlayerProfile
from app.services import settings_store

PRESETS = [
    ("PotPlayer", "link", "potplayer://{url}"),
    ("VLC", "link", "vlc://{url}"),
    ("IINA", "link", "iina://weblink?url={url_encoded}"),
    ("下載 m3u 清單", "m3u", ""),
]
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
BLOCKED = {"javascript", "data", "file", "vbscript", "blob", "about"}
PLACEHOLDERS = ("{url}", "{url_encoded}")


def seed_players(session: Session) -> None:
    if session.exec(select(PlayerProfile)).first() is not None:
        return
    for name, kind, template in PRESETS:
        session.add(PlayerProfile(name=name, kind=kind, template=template))
    session.commit()


def validate_profile(kind: str, template: str) -> None:
    if kind not in ("link", "m3u"):
        raise ValueError("類型必須是 link 或 m3u")
    if kind == "m3u":
        return
    if not any(p in template for p in PLACEHOLDERS):
        raise ValueError("樣板必須包含 {url} 或 {url_encoded}")
    match = SCHEME.match(template.strip())
    if not match:
        raise ValueError("樣板必須以協定開頭，例如 potplayer://")
    if match.group(0)[:-1].lower() in BLOCKED:
        raise ValueError("不允許這個協定")


def build_href(template: str, stream_url: str, filename: str) -> str:
    return (
        template.replace("{url_encoded}", quote(stream_url, safe=""))
        .replace("{url}", stream_url)
        .replace("{filename}", quote(filename, safe=""))
    )


def get_token(session: Session) -> str:
    token = settings_store.get_value(session, "stream_token")
    if not token:
        token = new_token(session)
    return token


def new_token(session: Session) -> str:
    token = secrets.token_urlsafe(16)
    settings_store.set_value(session, "stream_token", token)
    return token


def check_token(session: Session, given: str) -> bool:
    expected = settings_store.get_value(session, "stream_token")
    return bool(expected) and hmac.compare_digest(expected, given)
