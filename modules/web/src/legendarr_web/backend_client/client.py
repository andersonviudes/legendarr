from collections.abc import AsyncIterator

import httpx

from legendarr_web.config.settings import get_web_settings


async def get_backend_client() -> AsyncIterator[httpx.AsyncClient]:
    settings = get_web_settings()
    async with httpx.AsyncClient(base_url=settings.backend_api_url) as client:
        yield client


def error_detail(exc: httpx.HTTPStatusError) -> str:
    """Pull the backend's `detail` message out of an HTTPStatusError's JSON body."""
    try:
        return exc.response.json().get("detail", "Something went wrong. Please try again.")
    except ValueError:
        return "Something went wrong. Please try again."
