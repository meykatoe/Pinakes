import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/fs")

MAX_ENTRIES = 500


class DirOut(BaseModel):
    path: str
    parent: str | None
    dirs: list[str]


@router.get("/dirs")
def list_dirs(path: str = "") -> DirOut:
    target = Path(path or Path.home()).expanduser()
    if not target.is_absolute():
        raise HTTPException(422, "必須是絕對路徑")
    target = target.resolve()
    if not target.is_dir():
        raise HTTPException(404, "目錄不存在")
    try:
        with os.scandir(target) as it:
            names = sorted(
                (e.name for e in it if not e.name.startswith(".") and _is_dir(e)),
                key=str.casefold,
            )
    except PermissionError as exc:
        raise HTTPException(403, "沒有讀取權限") from exc
    parent = str(target.parent) if target.parent != target else None
    return DirOut(path=str(target), parent=parent, dirs=names[:MAX_ENTRIES])


def _is_dir(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False
