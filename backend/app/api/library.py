from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import Category
from app.services import categories as cat_service
from app.services import library, settings_store

router = APIRouter()

MEDIA_TYPES = {"movie", "tv"}


class PathsOut(BaseModel):
    inbox_path: str
    library_path: str
    # 硬連結需同磁碟
    same_device: bool | None


class PathsIn(BaseModel):
    inbox_path: str
    library_path: str


class CategoryIn(BaseModel):
    name: str
    media_type: str
    subdir: str


def _paths_out(session: Session) -> PathsOut:
    inbox = settings_store.get_value(session, "inbox_path")
    lib = settings_store.get_value(session, "library_path")
    same = library.same_device(inbox, lib) if inbox and lib else None
    return PathsOut(inbox_path=inbox, library_path=lib, same_device=same)


@router.get("/library/paths")
def read_paths(session: Session = Depends(get_session)) -> PathsOut:
    return _paths_out(session)


@router.put("/library/paths")
def update_paths(
    body: PathsIn, session: Session = Depends(get_session)
) -> PathsOut:
    inbox, lib = body.inbox_path.strip(), body.library_path.strip()
    try:
        library.validate_pair(inbox, lib)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    settings_store.set_value(session, "inbox_path", inbox)
    settings_store.set_value(session, "library_path", lib)
    return _paths_out(session)


@router.get("/categories")
def list_categories(session: Session = Depends(get_session)) -> list[Category]:
    return list(session.exec(select(Category).order_by(Category.id)))


def _validated(body: CategoryIn, session: Session, own_id: int | None) -> CategoryIn:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "名稱不可為空")
    if body.media_type not in MEDIA_TYPES:
        raise HTTPException(422, "類型必須是 movie 或 tv")
    try:
        subdir = cat_service.clean_subdir(body.subdir)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for field, value in (("name", name), ("subdir", subdir)):
        stmt = select(Category).where(getattr(Category, field) == value)
        found = session.exec(stmt).first()
        if found and found.id != own_id:
            raise HTTPException(409, "名稱或子目錄已存在")
    return CategoryIn(name=name, media_type=body.media_type, subdir=subdir)


@router.post("/categories", status_code=201)
def create_category(
    body: CategoryIn, session: Session = Depends(get_session)
) -> Category:
    data = _validated(body, session, None)
    category = Category(**data.model_dump())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.put("/categories/{category_id}")
def update_category(
    category_id: int, body: CategoryIn, session: Session = Depends(get_session)
) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "分類不存在")
    data = _validated(body, session, category_id)
    if category.builtin and data.media_type != category.media_type:
        raise HTTPException(422, "內建分類不可變更類型")
    category.name, category.media_type, category.subdir = (
        data.name,
        data.media_type,
        data.subdir,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int, session: Session = Depends(get_session)
) -> None:
    category = session.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "分類不存在")
    if category.builtin:
        raise HTTPException(422, "內建分類不可刪除")
    session.delete(category)
    session.commit()
