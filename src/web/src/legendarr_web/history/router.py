import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.history import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/history")
templates = get_templates("history")


@router.get("/")
async def show_history(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    entries = await service.get_history(client)
    return templates.TemplateResponse(request, "history.html", {"entries": entries})
