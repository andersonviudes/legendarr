from collections.abc import AsyncIterator

import httpx

from legendarr_web.config.settings import get_web_settings


async def get_backend_client() -> AsyncIterator[httpx.AsyncClient]:
    settings = get_web_settings()
    async with httpx.AsyncClient(base_url=settings.backend_api_url) as client:
        yield client
