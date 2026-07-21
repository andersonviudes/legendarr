from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.arr_services import service
from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/arr-services")
templates = get_templates("arr_services")

DEFAULT_PORTS = {"radarr": 7878, "sonarr": 8989}


async def _arr_service_form(
    service_type: str = Form(...),
    name: str = Form(...),
    enabled: bool = Form(False),
    host: str = Form(...),
    port: int = Form(...),
    base_url: str = Form("/"),
    use_ssl: bool = Form(False),
    http_timeout_seconds: int = Form(60),
    api_key: str = Form(""),
    remote_path_prefix: str = Form(""),
    local_path_prefix: str = Form(""),
) -> dict:
    return {
        "service_type": service_type,
        "name": name,
        "enabled": enabled,
        "host": host,
        "port": port,
        "base_url": base_url,
        "use_ssl": use_ssl,
        "http_timeout_seconds": http_timeout_seconds,
        "api_key": api_key,
        "remote_path_prefix": remote_path_prefix or None,
        "local_path_prefix": local_path_prefix or None,
    }


@router.get("/")
async def show_arr_services(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    services = await service.list_arr_services(client)
    return templates.TemplateResponse(
        request,
        "arr_services.html",
        {
            "radarr_services": [s for s in services if s["service_type"] == "radarr"],
            "sonarr_services": [s for s in services if s["service_type"] == "sonarr"],
        },
    )


@router.get("/count")
async def arr_services_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    services = await service.list_arr_services(client)
    return templates.TemplateResponse(
        request,
        "_count_badge.html",
        {"count": len(services)},
    )


@router.get("/new")
async def new_arr_service(request: Request, service_type: str):
    return templates.TemplateResponse(
        request,
        "arr_service_form.html",
        {
            "service": None,
            "service_type": service_type,
            "default_port": DEFAULT_PORTS.get(service_type, 80),
        },
    )


@router.get("/{service_id}/edit")
async def edit_arr_service(
    request: Request, service_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        existing = await service.get_arr_service(client, service_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        return RedirectResponse("/settings/arr-services/", status_code=303)
    return templates.TemplateResponse(
        request,
        "arr_service_form.html",
        {"service": existing, "service_type": existing["service_type"], "default_port": None},
    )


@router.post("/")
async def create_arr_service(
    request: Request,
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.create_arr_service(client, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "arr_service_form.html",
            {
                "service": data,
                "service_type": data["service_type"],
                "default_port": None,
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{data['service_type'].capitalize()} server added.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/arr-services/?{toast}", status_code=303)


@router.post("/test")
async def test_arr_service(
    request: Request,
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        result = await service.test_arr_service(client, data)
    except httpx.HTTPStatusError:
        # The probe itself returns 200 with a success flag; a non-2xx here means the
        # backend call failed outright, so show that instead of swapping an error page.
        result = {"success": False, "message": "Couldn't reach the backend to run the test."}
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/{service_id}/enabled")
async def toggle_arr_service_enabled(
    request: Request,
    service_id: int,
    enabled: bool = Form(False),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        updated = await service.set_arr_service_enabled(client, service_id, enabled)
    except httpx.HTTPStatusError:
        # Backend refused the change — re-render the switch in its prior state so the UI
        # doesn't drift out of sync with what's actually stored.
        updated = {"id": service_id, "enabled": not enabled}
    return templates.TemplateResponse(request, "_service_status.html", {"arr_service": updated})


@router.post("/{service_id}")
async def update_arr_service(
    request: Request,
    service_id: int,
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.update_arr_service(client, service_id, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return RedirectResponse("/settings/arr-services/", status_code=303)
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "arr_service_form.html",
            {
                "service": {**data, "id": service_id},
                "service_type": data["service_type"],
                "default_port": None,
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {"toast": f"{data['service_type'].capitalize()} server updated.", "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/arr-services/?{toast}", status_code=303)


@router.post("/{service_id}/delete")
async def delete_arr_service(
    service_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.delete_arr_service(client, service_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    return RedirectResponse("/settings/arr-services/", status_code=303)
