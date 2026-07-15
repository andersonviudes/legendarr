from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from legendarr_backend.bootstrap import build_scheduler

from legendarr_web.dashboard.router import router as dashboard_router
from legendarr_web.language_profiles.router import router as language_profiles_router
from legendarr_web.media_library.router import router as media_library_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="legendarr", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(dashboard_router)
    app.include_router(media_library_router)
    app.include_router(language_profiles_router)
    return app


app = create_app()
