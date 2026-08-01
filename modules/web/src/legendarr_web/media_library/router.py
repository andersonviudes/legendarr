import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.media_library import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


@router.get("/movies")
def show_movies(request: Request):
    return templates.TemplateResponse(request, "movies.html", {"movies": []})


@router.get("/series")
def show_series(request: Request):
    return templates.TemplateResponse(request, "series.html", {"series": []})


@router.post("/sync")
async def trigger_sync(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    try:
        await service.trigger_sync(client)
        result = {"success": True, "message": "Library sync started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the library sync."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
