import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.language_profiles import service
from legendarr_web.language_profiles.languages import SUPPORTED_LANGUAGES
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings")
templates = get_templates("language_profiles")


async def _language_profile_form(
    name: str = Form(...),
    source_languages: str = Form(...),
    target_languages: str = Form(...),
    extract_embedded_subtitles: bool = Form(False),
    forced: bool = Form(False),
    hearing_impaired: bool = Form(False),
    is_default: bool = Form(False),
) -> dict:
    return {
        "name": name,
        "source_languages": source_languages,
        "target_languages": target_languages,
        "extract_embedded_subtitles": extract_embedded_subtitles,
        "forced": forced,
        "hearing_impaired": hearing_impaired,
        "is_default": is_default,
    }


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


@router.get("/new")
async def new_language_profile(request: Request):
    return templates.TemplateResponse(
        request,
        "language_profile_form.html",
        {"profile": None, "languages": SUPPORTED_LANGUAGES},
    )


@router.get("/{profile_id}/edit")
async def edit_language_profile(
    request: Request, profile_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_language_profile(client, profile_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/", status_code=303)
    return templates.TemplateResponse(
        request,
        "language_profile_form.html",
        {"profile": existing, "languages": SUPPORTED_LANGUAGES},
    )


@router.post("/")
async def create_language_profile(
    request: Request,
    data: dict = Depends(_language_profile_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.create_language_profile(client, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "language_profile_form.html",
            {"profile": data, "error": error_detail(exc), "languages": SUPPORTED_LANGUAGES},
            status_code=exc.response.status_code,
        )
    return RedirectResponse("/settings/", status_code=303)


@router.post("/{profile_id}")
async def update_language_profile(
    request: Request,
    profile_id: int,
    data: dict = Depends(_language_profile_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.update_language_profile(client, profile_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "language_profile_form.html",
            {
                "profile": {**data, "id": profile_id},
                "error": error_detail(exc),
                "languages": SUPPORTED_LANGUAGES,
            },
            status_code=exc.response.status_code,
        )
    return RedirectResponse("/settings/", status_code=303)


@router.post("/{profile_id}/delete")
async def delete_language_profile(
    profile_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.delete_language_profile(client, profile_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    return RedirectResponse("/settings/", status_code=303)
