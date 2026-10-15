import os
from pathlib import Path


def validate_dir(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label}必須是絕對路徑")
    if not path.is_dir():
        raise ValueError(f"{label}不存在或不是目錄")
    return path.resolve()


def validate_pair(inbox: str, library: str) -> None:
    a = validate_dir(inbox, "待整理目錄") if inbox else None
    b = validate_dir(library, "已整理目錄") if library else None
    if a is None or b is None:
        return
    if a == b or a in b.parents or b in a.parents:
        raise ValueError("兩個目錄不可相同或互相包含")


def same_device(inbox: str, library: str) -> bool | None:
    try:
        return os.stat(inbox).st_dev == os.stat(library).st_dev
    except OSError:
        return None
