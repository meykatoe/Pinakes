import sys

from sqlmodel import Session

from app.db import get_engine, init_db
from app.services import settings_store

USAGE = "用法：python -m app.cli reset-password"


def main(argv: list[str]) -> int:
    if argv != ["reset-password"]:
        print(USAGE)
        return 2
    init_db()
    with Session(get_engine()) as session:
        settings_store.set_value(session, "auth_password", "")
    print("已清除登入密碼，請盡快在設定頁重新設定")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
