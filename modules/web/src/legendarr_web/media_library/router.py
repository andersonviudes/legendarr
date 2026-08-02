import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.media_library import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


@router.get("/movies")
async def show_movies(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    movies = await service.list_movies(client)
    return templates.TemplateResponse(request, "movies.html", {"movies": movies})


@router.get("/series")
async def show_series(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    series = await service.list_series(client)
    return templates.TemplateResponse(request, "series.html", {"series": series})


@router.post("/sync")
async def trigger_sync(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    try:
        await service.trigger_sync(client)
        result = {"success": True, "message": "Library sync started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the library sync."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
