import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.language_profiles import service
from legendarr_web.shared_kernel.backend_client.client import get_backend_client
from legendarr_web.shared_kernel.templates.loader import get_templates

router = APIRouter(prefix="/settings")
templates = get_templates("language_profiles")


@router.get("/")
async def show_language_profiles(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    profiles = await service.list_language_profiles(client)
    return templates.TemplateResponse(
        request,
        "language_profiles.html",
        {"profiles": profiles},
    )
