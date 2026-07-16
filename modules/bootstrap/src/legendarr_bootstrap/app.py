from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from legendarr_backend.api import create_api_app
from legendarr_backend.bootstrap import build_scheduler
from legendarr_web.app import create_app as create_web_app
from legendarr_web.backend_client.client import get_backend_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


def create_app() -> FastAPI:
    api_app = create_api_app()
    web_app = create_web_app()

    async def get_in_process_backend_client() -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api_app), base_url="http://backend/"
        ) as client:
            yield client

    web_app.dependency_overrides[get_backend_client] = get_in_process_backend_client

    app = FastAPI(title="legendarr", lifespan=lifespan)
    app.mount("/api", api_app)
    app.mount("/", web_app)
    return app


app = create_app()
