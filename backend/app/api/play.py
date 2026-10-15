import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import MediaItem, PlayerProfile
from app.services import fileops, organizer, player, settings_store

router = APIRouter()

mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("video/mp2t", ".ts")
mimetypes.add_type("video/mp2t", ".m2ts")


class PlayerIn(BaseModel):
    name: str
    kind: str = "link"
    template: str = ""
    enabled: bool = True


class PlayLink(BaseModel):
    player_id: int
    name: str
    kind: str
    href: str


class PlayOut(BaseModel):
    title: str
    stream_url: str
    links: list[PlayLink]


def _check(body: PlayerIn) -> PlayerIn:
    if not body.name.strip():
        raise HTTPException(422, "名稱不可為空")
    try:
        player.validate_profile(body.kind, body.template.strip())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return PlayerIn(
        name=body.name.strip(), kind=body.kind,
        template=body.template.strip(), enabled=body.enabled,
    )


@router.get("/players")
def list_players(session: Session = Depends(get_session)) -> list[PlayerProfile]:
    return list(session.exec(select(PlayerProfile).order_by(PlayerProfile.id)))


@router.post("/players", status_code=201)
def create_player(
    body: PlayerIn, session: Session = Depends(get_session)
) -> PlayerProfile:
    profile = PlayerProfile(**_check(body).model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.put("/players/{player_id}")
def update_player(
    player_id: int, body: PlayerIn, session: Session = Depends(get_session)
) -> PlayerProfile:
    profile = session.get(PlayerProfile, player_id)
    if profile is None:
        raise HTTPException(404, "播放器不存在")
    for key, value in _check(body).model_dump().items():
        setattr(profile, key, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/players/{player_id}", status_code=204)
def delete_player(player_id: int, session: Session = Depends(get_session)) -> None:
    profile = session.get(PlayerProfile, player_id)
    if profile is None:
        raise HTTPException(404, "播放器不存在")
    session.delete(profile)
    session.commit()


def base_url(request: Request, session: Session) -> str:
    override = settings_store.get_value(session, "public_base_url")
    return override or str(request.base_url).rstrip("/")


def playable_item(session: Session, item_id: int) -> tuple[MediaItem, Path]:
    item = session.get(MediaItem, item_id)
    if item is None or item.status != "done" or not item.target_path:
        raise HTTPException(404, "找不到可播放的檔案")
    try:
        _, library = organizer.get_roots(session)
        path = Path(item.target_path)
        fileops.ensure_within(path, library)
    except (organizer.OrganizeError, fileops.FileOpError) as exc:
        raise HTTPException(404, "找不到可播放的檔案") from exc
    if not path.is_file():
        raise HTTPException(404, "檔案不存在")
    return item, path


def stream_url(base: str, item_id: int, name: str, token: str) -> str:
    return f"{base}/api/stream/{item_id}/{quote(name, safe='')}?token={token}"


@router.get("/play/{item_id}")
def play_links(
    item_id: int, request: Request, session: Session = Depends(get_session)
) -> PlayOut:
    item, path = playable_item(session, item_id)
    token = player.get_token(session)
    base = base_url(request, session)
    stream = stream_url(base, item_id, path.name, token)
    links = []
    stmt = select(PlayerProfile).where(PlayerProfile.enabled).order_by(PlayerProfile.id)
    for profile in session.exec(stmt):
        if profile.kind == "m3u":
            href = f"{base}/api/stream/{item_id}/playlist.m3u?token={token}"
        else:
            href = player.build_href(profile.template, stream, path.name)
        links.append(
            PlayLink(
                player_id=profile.id, name=profile.name, kind=profile.kind, href=href
            )
        )
    return PlayOut(title=item.title or path.stem, stream_url=stream, links=links)


@router.post("/play/token/regenerate")
def regenerate_token(session: Session = Depends(get_session)) -> dict[str, bool]:
    player.new_token(session)
    return {"ok": True}


@router.get("/stream/{item_id}/playlist.m3u")
def playlist(
    item_id: int,
    request: Request,
    token: str = "",
    session: Session = Depends(get_session),
) -> PlainTextResponse:
    if not player.check_token(session, token):
        raise HTTPException(403, "權杖錯誤")
    item, path = playable_item(session, item_id)
    stream = stream_url(base_url(request, session), item_id, path.name, token)
    title = " ".join((item.title or path.stem).split())
    body = f"#EXTM3U\n#EXTINF:-1,{title}\n{stream}\n"
    return PlainTextResponse(
        body,
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": 'attachment; filename="play.m3u"'},
    )


@router.api_route("/stream/{item_id}/{filename}", methods=["GET", "HEAD"])
def stream(
    item_id: int,
    filename: str,
    token: str = "",
    session: Session = Depends(get_session),
) -> FileResponse:
    if not player.check_token(session, token):
        raise HTTPException(403, "權杖錯誤")
    _, path = playable_item(session, item_id)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
