from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.subtitle_translation import service
from legendarr_web.subtitle_translation.provider_display import (
    provider_credential_fields,
    provider_label,
)
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/translation-providers")
templates = get_templates("subtitle_translation")


def _with_display(provider: dict) -> dict:
    return {
        **provider,
        "label": provider_label(provider["kind"]),
        "credential_fields": provider_credential_fields(provider["kind"]),
    }


async def _credential_form(
    kind: str = Form(...),
    api_key: str = Form(""),
    endpoint: str = Form(""),
    model: str = Form(""),
) -> dict:
    return {"kind": kind, "api_key": api_key, "endpoint": endpoint, "model": model}


@router.get("/")
async def show_translation_providers(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    providers = await service.list_translation_providers(client)
    defaults = await service.get_translation_defaults(client)
    return templates.TemplateResponse(
        request,
        "translation_providers.html",
        {
            "providers": [_with_display(p) for p in providers],
            "default_translation_provider": defaults["default_translation_provider"],
            "active_tab": "translation",
        },
    )


@router.get("/{provider_id}/edit")
async def edit_translation_provider(
    request: Request, provider_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_translation_provider(client, provider_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/translation-providers/", status_code=303)
    return templates.TemplateResponse(
        request,
        "translation_provider_form.html",
        {"provider": _with_display(existing)},
    )


@router.post("/{provider_id}")
async def update_translation_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.update_translation_provider(client, provider_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/translation-providers/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "translation_provider_form.html",
            {
                "provider": _with_display({**data, "id": provider_id}),
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{provider_label(updated['kind'])} updated.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/translation-providers/?{toast}", status_code=303)


@router.post("/{provider_id}/enabled")
async def toggle_translation_provider_enabled(
    request: Request,
    provider_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_translation_provider_enabled(client, provider_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored. Reaching this route at all
        # means the switch was rendered, which only happens for a configured provider.
        updated = {"id": provider_id, "enabled": not enabled, "is_configured": True}
    return templates.TemplateResponse(
        request,
        "_provider_status.html",
        {"provider": updated, "toggle_url_prefix": "/settings/translation-providers/"},
    )


@router.post("/{provider_id}/default")
async def set_default_translation_provider(
    request: Request,
    provider_id: int,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        provider = await service.get_translation_provider(client, provider_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/translation-providers/", status_code=303)
    try:
        await service.set_default_translation_provider(client, provider["kind"])
        default_translation_provider = provider["kind"]
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the grid with whatever the default
        # actually is now, so the UI doesn't drift out of sync with what's stored.
        defaults = await service.get_translation_defaults(client)
        default_translation_provider = defaults["default_translation_provider"]
    providers = await service.list_translation_providers(client)
    return templates.TemplateResponse(
        request,
        "_provider_grid.html",
        {
            "providers": [_with_display(p) for p in providers],
            "default_translation_provider": default_translation_provider,
        },
    )


@router.post("/{provider_id}/test")
async def test_translation_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_translation_provider(client, provider_id, data)
    except httpx.HTTPStatusError:
        # The probe itself returns 200 with a success flag; a non-2xx here means the
        # backend call failed outright, so show that instead of swapping an error page.
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
