import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.language_profiles import service
from legendarr_web.shared_kernel.backend_client import get_backend_client
from legendarr_web.shared_kernel.templates import get_templates

router = APIRouter()
templates = get_templates("dashboard")


@router.get("/")
async def show_dashboard(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    profiles = await service.list_language_profiles(client)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "profile_count": len(profiles),
            "sync_interval_minutes": None,
            "next_sync_minutes": None,
        },
    )
