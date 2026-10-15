from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
NO_CACHE = {"Cache-Control": "no-cache"}


def mount_frontend(app: FastAPI, root: Path) -> None:
    root = root.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "Not Found")
        if not index.is_file():
            raise HTTPException(404, "前端尚未建置，請在 frontend 執行 npm run build")
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            headers = IMMUTABLE if path.startswith("assets/") else NO_CACHE
            return FileResponse(target, headers=headers)
        return FileResponse(index, headers=NO_CACHE)
