import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app import __version__
from app.api import auth as auth_api
from app.api import (
    fs,
    health,
    hls,
    library,
    match,
    media,
    organize,
    play,
    rules,
    subtitles,
    sync,
    watch,
)
from app.api import settings as settings_api
from app.config import settings
from app.db import get_engine, init_db
from app.services import auth, precache, rclone_sync, transcode, watcher
from app.web import mount_frontend

# 免登入路徑
PUBLIC = ("/api/health", "/api/auth/", "/api/stream/")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.watch_loop:
        reaper = asyncio.create_task(transcode.reaper())
        cacher = asyncio.create_task(precache.worker())
        try:
            async with watcher.background(), rclone_sync.background():
                yield
        finally:
            for task in (reaper, cacher):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
    else:
        yield


app = FastAPI(title="Pinakes", version=__version__, lifespan=lifespan)



@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(PUBLIC):
        with Session(get_engine()) as session:
            stored = auth.stored_hash(session)
        if not auth.is_authenticated(request, stored):
            return JSONResponse({"detail": "請先登入"}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROUTERS = (
    health, auth_api, settings_api, fs, library, rules, match, organize, watch, sync, media,
    play, hls, subtitles,
)
for module in ROUTERS:
    app.include_router(module.router, prefix="/api")

mount_frontend(app, settings.static_dir)
