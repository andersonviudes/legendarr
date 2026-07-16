import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.arr_services import service
from legendarr_web.backend_client.client import get_backend_client
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
    api_key: str = Form(...),
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
    existing = await service.get_arr_service(client, service_id)
    return templates.TemplateResponse(
        request,
        "arr_service_form.html",
        {"service": existing, "service_type": existing["service_type"], "default_port": None},
    )


@router.post("/")
async def create_arr_service(
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    await service.create_arr_service(client, data)
    return RedirectResponse("/settings/arr-services/", status_code=303)


@router.post("/test")
async def test_arr_service(
    request: Request,
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    result = await service.test_arr_service(client, data)
    return templates.TemplateResponse(request, "_test_result.html", {"result": result})


@router.post("/{service_id}")
async def update_arr_service(
    service_id: int,
    data: dict = Depends(_arr_service_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    await service.update_arr_service(client, service_id, data)
    return RedirectResponse("/settings/arr-services/", status_code=303)


@router.post("/{service_id}/delete")
async def delete_arr_service(
    service_id: int, client: httpx.AsyncClient = Depends(get_backend_client)
):
    await service.delete_arr_service(client, service_id)
    return RedirectResponse("/settings/arr-services/", status_code=303)
