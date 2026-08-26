from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.media_servers import service
from legendarr_web.media_servers.provider_display import provider_label
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/media-servers")
templates = get_templates("media_servers")


def _with_display(server: dict) -> dict:
    return {**server, "label": provider_label(server["kind"])}


async def _credential_form(
    kind: str = Form(...), base_url: str = Form(""), token: str = Form("")
) -> dict:
    return {"kind": kind, "base_url": base_url, "token": token}


@router.get("/")
async def show_media_servers(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    servers = await service.list_media_servers(client)
    return templates.TemplateResponse(
        request, "media_servers.html", {"servers": [_with_display(s) for s in servers]}
    )


@router.get("/count")
async def media_servers_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    servers = await service.list_media_servers(client)
    enabled_count = sum(1 for server in servers if server["enabled"])
    return templates.TemplateResponse(request, "_count_badge.html", {"count": enabled_count})


@router.get("/{server_id}/edit")
async def edit_media_server(
    request: Request, server_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_media_server(client, server_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/media-servers/", status_code=303)
    return templates.TemplateResponse(
        request, "media_server_form.html", {"server": _with_display(existing)}
    )


@router.post("/{server_id}")
async def update_media_server(
    request: Request,
    server_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.update_media_server(client, server_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/media-servers/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "media_server_form.html",
            {"server": _with_display({**data, "id": server_id}), "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{provider_label(updated['kind'])} updated.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/media-servers/?{toast}", status_code=303)


@router.post("/{server_id}/enabled")
async def toggle_media_server_enabled(
    request: Request,
    server_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_media_server_enabled(client, server_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored. Reaching this route at
        # all means the switch was rendered, which only happens for a configured server.
        updated = {"id": server_id, "enabled": not enabled, "is_configured": True}
    return templates.TemplateResponse(
        request,
        "_server_status.html",
        {"provider": updated, "toggle_url_prefix": "/settings/media-servers/"},
    )


@router.post("/{server_id}/test")
async def test_media_server(
    request: Request,
    server_id: int,
    data: dict = Depends(_credential_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_media_server(client, server_id, data)
    except httpx.HTTPStatusError:
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})
