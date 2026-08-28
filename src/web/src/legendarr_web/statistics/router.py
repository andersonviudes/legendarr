import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.statistics import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/statistics")
templates = get_templates("statistics")


@router.get("/")
async def show_statistics(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    statistics = await service.get_statistics(client)
    return templates.TemplateResponse(request, "statistics.html", {"statistics": statistics})
