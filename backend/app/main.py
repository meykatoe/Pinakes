from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, library, match, media, organize, play, rules, watch
from app.api import settings as settings_api
from app.config import settings
from app.db import init_db
from app.services import watcher


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.watch_loop:
        async with watcher.background():
            yield
    else:
        yield


app = FastAPI(title="Pinakes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (health, settings_api, library, rules, match, organize, watch, media, play):
    app.include_router(module.router, prefix="/api")
