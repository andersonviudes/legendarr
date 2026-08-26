import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.language_profiles import service
from legendarr_web.media_library import service as media_library_service
from legendarr_web.subtitle_acquisition import service as subtitle_acquisition_service
from legendarr_web.subtitle_translation import service as subtitle_translation_service
from legendarr_web.templates.loader import get_templates

router = APIRouter()
templates = get_templates("dashboard")


@router.get("/")
async def show_dashboard(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    profiles = await service.list_language_profiles(client)
    wanted = await media_library_service.list_wanted(client)
    subtitle_providers = await subtitle_acquisition_service.list_subtitle_providers(client)
    translation_providers = await subtitle_translation_service.list_translation_providers(client)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "profile_count": len(profiles),
            "sync_interval_minutes": None,
            "next_sync_minutes": None,
            "movies_missing_count": sum(1 for item in wanted if item["kind"] == "movie"),
            "series_missing_count": sum(1 for item in wanted if item["kind"] == "series"),
            "subtitle_providers_enabled": sum(1 for p in subtitle_providers if p["enabled"]),
            "subtitle_providers_total": len(subtitle_providers),
            "translation_providers_enabled": sum(1 for p in translation_providers if p["enabled"]),
            "translation_providers_total": len(translation_providers),
        },
    )
