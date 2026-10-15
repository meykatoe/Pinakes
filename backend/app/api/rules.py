from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import ParseRule
from app.services import naming, pipeline, rules, settings_store

router = APIRouter()


class RuleIn(BaseModel):
    name: str
    pattern: str
    priority: int = 100
    enabled: bool = True
    media_type: str | None = None


class NamingIO(BaseModel):
    movie_template: str
    tv_template: str


class PreviewIn(BaseModel):
    path: str


class PreviewOut(BaseModel):
    parsed: dict
    rule: str | None
    target: str | None
    error: str | None = None


def _check_rule(body: RuleIn) -> None:
    if not body.name.strip():
        raise HTTPException(422, "名稱不可為空")
    if body.media_type not in (None, "movie", "tv"):
        raise HTTPException(422, "類型必須是 movie 或 tv")
    try:
        rules.validate_pattern(body.pattern)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _ordered(session: Session) -> list[ParseRule]:
    stmt = select(ParseRule).order_by(ParseRule.priority, ParseRule.id)
    return list(session.exec(stmt))


@router.get("/rules")
def list_rules(session: Session = Depends(get_session)) -> list[ParseRule]:
    return _ordered(session)


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, session: Session = Depends(get_session)) -> ParseRule:
    _check_rule(body)
    rule = ParseRule(**body.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: int, body: RuleIn, session: Session = Depends(get_session)
) -> ParseRule:
    rule = session.get(ParseRule, rule_id)
    if rule is None:
        raise HTTPException(404, "規則不存在")
    _check_rule(body)
    for key, value in body.model_dump().items():
        setattr(rule, key, value)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> None:
    rule = session.get(ParseRule, rule_id)
    if rule is None:
        raise HTTPException(404, "規則不存在")
    session.delete(rule)
    session.commit()


@router.get("/naming")
def read_naming(session: Session = Depends(get_session)) -> NamingIO:
    return NamingIO(
        movie_template=settings_store.get_value(session, "movie_template"),
        tv_template=settings_store.get_value(session, "tv_template"),
    )


@router.put("/naming")
def update_naming(
    body: NamingIO, session: Session = Depends(get_session)
) -> NamingIO:
    for key in ("movie_template", "tv_template"):
        value = getattr(body, key).strip()
        try:
            naming.validate_template(value)
        except ValueError as exc:
            raise HTTPException(422, f"{key}：{exc}") from exc
        settings_store.set_value(session, key, value)
    return read_naming(session)


@router.post("/parse/preview")
def preview(body: PreviewIn, session: Session = Depends(get_session)) -> PreviewOut:
    parts = [p for p in body.path.replace("\\", "/").split("/") if p]
    if not parts:
        raise HTTPException(422, "路徑不可為空")
    parsed = pipeline.parse_file(session, parts)
    key = "tv_template" if parsed.media_type == "tv" else "movie_template"
    template = settings_store.get_value(session, key)
    values = {**parsed.__dict__, "original_title": parsed.title}
    target, error = None, None
    try:
        target = naming.render(template, values, parsed.ext)
    except ValueError as exc:
        error = str(exc)
    data = {k: v for k, v in parsed.__dict__.items() if k != "rule"}
    return PreviewOut(parsed=data, rule=parsed.rule, target=target, error=error)
