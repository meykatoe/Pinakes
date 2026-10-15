from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.services import auth, settings_store

router = APIRouter(prefix="/auth")


class StatusOut(BaseModel):
    enabled: bool
    authenticated: bool


class LoginIn(BaseModel):
    password: str


class PasswordIn(BaseModel):
    current: str = ""
    # 空字串為停用
    new: str = ""


def _set_cookie(request: Request, response: Response, stored: str) -> None:
    response.set_cookie(
        auth.COOKIE,
        auth.make_token(stored),
        max_age=auth.MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/status")
def status(request: Request, session: Session = Depends(get_session)) -> StatusOut:
    stored = auth.stored_hash(session)
    return StatusOut(
        enabled=bool(stored), authenticated=auth.is_authenticated(request, stored)
    )


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> StatusOut:
    stored = auth.stored_hash(session)
    if not stored:
        return StatusOut(enabled=False, authenticated=True)
    ip = _client(request)
    if auth.throttled(ip):
        raise HTTPException(429, "嘗試次數過多，請 5 分鐘後再試")
    if not auth.verify_password(body.password, stored):
        auth.record_fail(ip)
        raise HTTPException(401, "密碼錯誤")
    auth.clear_fails(ip)
    _set_cookie(request, response, stored)
    return StatusOut(enabled=True, authenticated=True)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(auth.COOKIE)


@router.put("/password")
def change_password(
    body: PasswordIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> StatusOut:
    stored = auth.stored_hash(session)
    if stored:
        if not auth.is_authenticated(request, stored):
            raise HTTPException(401, "請先登入")
        if not auth.verify_password(body.current, stored):
            raise HTTPException(422, "目前密碼錯誤")
    if not body.new:
        settings_store.set_value(session, "auth_password", "")
        response.delete_cookie(auth.COOKIE)
        return StatusOut(enabled=False, authenticated=True)
    if len(body.new) < auth.MIN_LENGTH:
        raise HTTPException(422, f"密碼至少需要 {auth.MIN_LENGTH} 個字元")
    new_hash = auth.hash_password(body.new)
    settings_store.set_value(session, "auth_password", new_hash)
    _set_cookie(request, response, new_hash)
    return StatusOut(enabled=True, authenticated=True)
