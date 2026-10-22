"""版本號工具：以 backend/pyproject.toml 為準，同步其他檔案。

用法：
    python scripts/version.py show
    python scripts/version.py check [--tag v1.2.0]
    python scripts/version.py set 1.2.0
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# 檔案、取代樣式（第一組為版本號）
TARGETS = {
    "backend/pyproject.toml": r'(?m)^version\s*=\s*"([^"]+)"',
    "backend/app/__init__.py": r'(?m)^__version__\s*=\s*"([^"]+)"',
    "backend/uv.lock": r'(?m)^name = "pinakes"\nversion = "([^"]+)"',
    "frontend/package.json": r'(?m)^  "version":\s*"([^"]+)"',
    "frontend/package-lock.json": r'(?s)\A\{\s*"name": "pinakes-frontend",\s*"version": "([^"]+)"',
}
# 同一檔案的第二處
EXTRA = {
    "frontend/package-lock.json": r'(?s)"packages": \{\s*"": \{\s*"name": "pinakes-frontend",\s*"version": "([^"]+)"',
}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def find(rel: str) -> str:
    m = re.search(TARGETS[rel], read(rel))
    if not m:
        sys.exit(f"找不到版本號：{rel}")
    extra = EXTRA.get(rel)
    if extra:
        e = re.search(extra, read(rel))
        if not e:
            sys.exit(f"找不到版本號：{rel}")
        if e.group(1) != m.group(1):
            return f"{m.group(1)}/{e.group(1)}"
    return m.group(1)


def replace(rel: str, new: str) -> None:
    text = read(rel)
    for pattern in (TARGETS[rel], EXTRA.get(rel)):
        if pattern is None:
            continue
        m = re.search(pattern, text)
        if not m:
            sys.exit(f"找不到版本號：{rel}")
        text = text[: m.start(1)] + new + text[m.end(1) :]
    (ROOT / rel).write_text(text, encoding="utf-8", newline="")


def show() -> int:
    for rel in TARGETS:
        print(f"{find(rel):<10}{rel}")
    return 0


def check(tag: str | None) -> int:
    base = find("backend/pyproject.toml")
    bad = [rel for rel in TARGETS if find(rel) != base]
    for rel in bad:
        print(f"版本不一致：{rel} 是 {find(rel)}，應為 {base}")
    if tag is not None and tag.removeprefix("v") != base:
        print(f"標籤 {tag} 與程式版本 {base} 不一致")
        bad.append("tag")
    if bad:
        return 1
    print(f"版本一致：{base}")
    return 0


def set_version(new: str) -> int:
    if not SEMVER.match(new):
        sys.exit(f"版本格式應為 X.Y.Z：{new}")
    for rel in TARGETS:
        replace(rel, new)
    print(f"已更新為 {new}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="同步版本號")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    c = sub.add_parser("check")
    c.add_argument("--tag")
    s = sub.add_parser("set")
    s.add_argument("version")
    args = p.parse_args()
    if args.cmd == "show":
        return show()
    if args.cmd == "check":
        return check(args.tag)
    return set_version(args.version)


if __name__ == "__main__":
    sys.exit(main())
