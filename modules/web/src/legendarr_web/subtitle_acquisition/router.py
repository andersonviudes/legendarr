from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.subtitle_acquisition import service
from legendarr_web.subtitle_acquisition.provider_display import (
    provider_credential_fields,
    provider_label,
    provider_search_options,
)
from legendarr_web.subtitle_proxies import service as proxy_service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/subtitle-providers")
templates = get_templates("subtitle_acquisition")


def _with_display(provider: dict) -> dict:
    return {
        **provider,
        "label": provider_label(provider["kind"]),
        "credential_fields": provider_credential_fields(provider["kind"]),
        "search_options": provider_search_options(provider["kind"]),
    }


def _proxy_options(proxies: list[dict]) -> list[tuple[str, str]]:
    return [("", "None")] + [(str(proxy["id"]), proxy["name"]) for proxy in proxies]


async def _credential_form(
    kind: str = Form(...),
    api_key: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    proxy_id: str = Form(""),
    use_hash: bool = Form(False),
    include_ai_translated: bool = Form(False),
    include_machine_translated: bool = Form(False),
) -> dict:
    # Every submit carries all three search-option fields regardless of `kind`, since an
    # unchecked HTML checkbox is indistinguishable from "this kind doesn't render it" —
    # only include them for a kind that actually has them, or the backend's presence-based
    # merge (`model_fields_set`) would silently zero them out on, say, an Addic7ed save.
    search_options = {
        "use_hash": use_hash,
        "include_ai_translated": include_ai_translated,
        "include_machine_translated": include_machine_translated,
    }
    return {
        "kind": kind,
        "api_key": api_key,
        "username": username,
        "password": password,
        "proxy_id": int(proxy_id) if proxy_id else None,
        **{k: v for k, v in search_options.items() if k in provider_search_options(kind)},
    }


@router.get("/")
async def show_subtitle_providers(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    providers = await service.list_subtitle_providers(client)
    return templates.TemplateResponse(
        request,
        "subtitle_providers.html",
        {"providers": [_with_display(p) for p in providers]},
    )


@router.get("/count")
async def subtitle_providers_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    providers = await service.list_subtitle_providers(client)
    enabled_count = sum(1 for provider in providers if provider["enabled"])
    return templates.TemplateResponse(request, "_count_badge.html", {"count": enabled_count})


@router.get("/{provider_id}/edit")
async def edit_subtitle_provider(
    request: Request, provider_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_subtitle_provider(client, provider_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/subtitle-providers/", status_code=303)
    proxies = await proxy_service.list_subtitle_proxies(client)
    return templates.TemplateResponse(
        request,
        "subtitle_provider_form.html",
        {"provider": _with_display(existing), "proxy_options": _proxy_options(proxies)},
    )


@router.post("/{provider_id}")
async def update_subtitle_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.update_subtitle_provider(client, provider_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/subtitle-providers/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        proxies = await proxy_service.list_subtitle_proxies(client)
        return templates.TemplateResponse(
            request,
            "subtitle_provider_form.html",
            {
                "provider": _with_display({**data, "id": provider_id}),
                "proxy_options": _proxy_options(proxies),
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{provider_label(updated['kind'])} updated.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/subtitle-providers/?{toast}", status_code=303)


@router.post("/{provider_id}/enabled")
async def toggle_subtitle_provider_enabled(
    request: Request,
    provider_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_subtitle_provider_enabled(client, provider_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored. Reaching this route at all
        # means the switch was rendered, which only happens for a configured provider.
        updated = {"id": provider_id, "enabled": not enabled, "is_configured": True}
    return templates.TemplateResponse(request, "_provider_status.html", {"provider": updated})


@router.post("/{provider_id}/test")
async def test_subtitle_provider(
    request: Request,
    provider_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_subtitle_provider(client, provider_id, data)
    except httpx.HTTPStatusError:
        # The probe itself returns 200 with a success flag; a non-2xx here means the
        # backend call failed outright, so show that instead of swapping an error page.
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
