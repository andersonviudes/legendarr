from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.media_metadata import service
from legendarr_web.media_metadata.provider_display import provider_label
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/metadata-source")
templates = get_templates("media_metadata")


def _with_display(provider: dict) -> dict:
    return {**provider, "label": provider_label(provider["kind"])}


async def _credential_form(kind: str = Form(...), api_key: str = Form("")) -> dict:
    return {"kind": kind, "api_key": api_key}


@router.get("/")
async def show_metadata_providers(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    providers = await service.list_metadata_providers(client)
    return templates.TemplateResponse(
        request, "metadata_providers.html", {"providers": [_with_display(p) for p in providers]}
    )


@router.get("/count")
async def metadata_providers_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    providers = await service.list_metadata_providers(client)
    enabled_count = sum(1 for provider in providers if provider["enabled"])
    return templates.TemplateResponse(request, "_count_badge.html", {"count": enabled_count})


@router.get("/{provider_id}/edit")
async def edit_metadata_provider(
    request: Request, provider_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_metadata_provider(client, provider_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/metadata-source/", status_code=303)
    return templates.TemplateResponse(
        request, "metadata_provider_form.html", {"provider": _with_display(existing)}
    )


@router.post("/refetch")
async def trigger_metadata_refetch(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.trigger_metadata_refetch(client)
        result = {"success": True, "message": "Metadata refetch started."}
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't start the metadata refetch."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/{provider_id}")
async def update_metadata_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.update_metadata_provider(client, provider_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/metadata-source/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "metadata_provider_form.html",
            {"provider": _with_display({**data, "id": provider_id}), "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{provider_label(updated['kind'])} updated.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/metadata-source/?{toast}", status_code=303)


@router.post("/{provider_id}/enabled")
async def toggle_metadata_provider_enabled(
    request: Request,
    provider_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_metadata_provider_enabled(client, provider_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored. Reaching this route at
        # all means the switch was rendered, which only happens for a configured provider.
        updated = {"id": provider_id, "enabled": not enabled, "is_configured": True}
    return templates.TemplateResponse(
        request,
        "_provider_status.html",
        {"provider": updated, "toggle_url_prefix": "/settings/metadata-source/"},
    )


@router.post("/{provider_id}/test")
async def test_metadata_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_metadata_provider(client, provider_id, data)
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
