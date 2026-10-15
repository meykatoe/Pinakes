from pathlib import PurePosixPath, PureWindowsPath

from sqlmodel import Session, select

from app.models import Category

BUILTIN = [
    ("電影", "movie", "電影"),
    ("影集", "tv", "影集"),
]


def seed_categories(session: Session) -> None:
    if session.exec(select(Category)).first() is not None:
        return
    for name, media_type, subdir in BUILTIN:
        session.add(
            Category(name=name, media_type=media_type, subdir=subdir, builtin=True)
        )
    session.commit()


def clean_subdir(subdir: str) -> str:
    value = subdir.strip().replace("\\", "/")
    if not value.strip("/"):
        raise ValueError("子目錄不可為空")
    posix = PurePosixPath(value)
    if posix.is_absolute() or PureWindowsPath(value).drive or ".." in posix.parts:
        raise ValueError("子目錄必須是相對路徑")
    return str(PurePosixPath(value.rstrip("/")))
