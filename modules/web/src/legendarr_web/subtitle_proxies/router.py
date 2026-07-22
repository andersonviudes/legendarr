from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.subtitle_proxies import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/subtitle-proxies")
templates = get_templates("subtitle_proxies")


async def _subtitle_proxy_form(
    name: str = Form(...),
    enabled: bool = Form(False),
    host: str = Form(...),
) -> dict:
    return {"name": name, "enabled": enabled, "host": host}


@router.get("/")
async def show_subtitle_proxies(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    proxies = await service.list_subtitle_proxies(client)
    return templates.TemplateResponse(request, "proxies.html", {"proxies": proxies})


@router.get("/count")
async def subtitle_proxies_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    proxies = await service.list_subtitle_proxies(client)
    return templates.TemplateResponse(request, "_count_badge.html", {"count": len(proxies)})


@router.get("/new")
async def new_subtitle_proxy(request: Request):
    return templates.TemplateResponse(request, "proxy_form.html", {"proxy": None})


@router.get("/{proxy_id}/edit")
async def edit_subtitle_proxy(
    request: Request, proxy_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_subtitle_proxy(client, proxy_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/subtitle-proxies/", status_code=303)
    return templates.TemplateResponse(request, "proxy_form.html", {"proxy": existing})


@router.post("/")
async def create_subtitle_proxy(
    request: Request,
    data: dict = Depends(_subtitle_proxy_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.create_subtitle_proxy(client, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "proxy_form.html",
            {"proxy": data, "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    toast = urlencode({"toast": f"{data['name']} added.", "toast_type": "success"})
    return RedirectResponse(f"/settings/subtitle-proxies/?{toast}", status_code=303)


@router.post("/test")
async def test_subtitle_proxy(
    request: Request,
    data: dict = Depends(_subtitle_proxy_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_subtitle_proxy(client, data)
    except httpx.HTTPStatusError:
        # The probe itself returns 200 with a success flag; a non-2xx here means the
        # backend call failed outright, so show that instead of swapping an error page.
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/{proxy_id}/enabled")
async def toggle_subtitle_proxy_enabled(
    request: Request,
    proxy_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_subtitle_proxy_enabled(client, proxy_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored.
        updated = {"id": proxy_id, "enabled": not enabled}
    return templates.TemplateResponse(request, "_proxy_status.html", {"proxy": updated})


@router.post("/{proxy_id}")
async def update_subtitle_proxy(
    request: Request,
    proxy_id: int,
    data: dict = Depends(_subtitle_proxy_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.update_subtitle_proxy(client, proxy_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/subtitle-proxies/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "proxy_form.html",
            {"proxy": {**data, "id": proxy_id}, "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    toast = urlencode({"toast": f"{data['name']} updated.", "toast_type": "success"})
    return RedirectResponse(f"/settings/subtitle-proxies/?{toast}", status_code=303)


@router.post("/{proxy_id}/delete")
async def delete_subtitle_proxy(
    proxy_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.delete_subtitle_proxy(client, proxy_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    return RedirectResponse("/settings/subtitle-proxies/", status_code=303)
