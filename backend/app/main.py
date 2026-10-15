import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, hls, library, match, media, organize, play, rules, watch
from app.api import settings as settings_api
from app.config import settings
from app.db import init_db
from app.services import transcode, watcher


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.watch_loop:
        reaper = asyncio.create_task(transcode.reaper())
        try:
            async with watcher.background():
                yield
        finally:
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
    else:
        yield


app = FastAPI(title="Pinakes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, settings_api, library, rules, match, organize, watch, media, play, hls):
    app.include_router(module.router, prefix="/api")
