import errno
import os
import shutil
from pathlib import Path

MODES = ("hardlink", "move", "copy", "symlink")
TRASH_DIR = ".pinakes-trash"


class FileOpError(Exception):
    pass


def ensure_within(path: Path, root: Path) -> None:
    resolved, base = path.resolve(), root.resolve()
    if base != resolved and base not in resolved.parents:
        raise FileOpError("路徑超出允許範圍")


def exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def place(mode: str, src: Path, dst: Path) -> None:
    if mode not in MODES:
        raise FileOpError(f"不支援的整理模式：{mode}")
    if exists(dst):
        raise FileOpError("目標已存在")
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if mode == "hardlink":
            os.link(src, dst)
        elif mode == "symlink":
            os.symlink(src, dst)
        elif mode == "copy":
            _copy(src, dst)
        else:
            _move(src, dst)
    except OSError as exc:
        if mode == "hardlink" and exc.errno == errno.EXDEV:
            raise FileOpError("來源與目標不在同一磁碟，無法建立硬連結") from exc
        raise FileOpError(f"檔案操作失敗：{exc.strerror or exc}") from exc


def _copy(src: Path, dst: Path) -> None:
    tmp = dst.with_name(dst.name + ".pinakes-tmp")
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def _move(src: Path, dst: Path) -> None:
    try:
        os.rename(src, dst)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        _copy(src, dst)
        if dst.stat().st_size != src.stat().st_size:
            dst.unlink(missing_ok=True)
            raise FileOpError("跨磁碟移動後大小不符")
        src.unlink()


def backup_existing(dst: Path, library: Path, stamp: str) -> Path:
    rel = dst.resolve().relative_to(library.resolve())
    target = library / TRASH_DIR / stamp / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(dst, target)
    return target


def prune_empty(start: Path, stop: Path) -> None:
    stop = stop.resolve()
    current = start.resolve()
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def revert(action: str, src: Path, dst: Path, backup: str, library: Path) -> None:
    if action == "move":
        if exists(dst):
            if exists(src):
                raise FileOpError("原位置已有檔案，無法還原")
            src.parent.mkdir(parents=True, exist_ok=True)
            _move(dst, src)
    elif exists(dst):
        dst.unlink()
    if backup and Path(backup).exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(backup, dst)
    prune_empty(dst.parent, library)
