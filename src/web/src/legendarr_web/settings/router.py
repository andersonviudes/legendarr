from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.i18n.translator import SUPPORTED_UI_LOCALES, current_locale, translate
from legendarr_web.settings import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/tasks")
templates = get_templates("settings")


async def _task_settings_form(
    sync_interval_minutes: int = Form(...),
    sync_retry_attempts: int = Form(...),
    sync_retry_delay_seconds: float = Form(...),
    sync_max_instances: int = Form(...),
    sync_coalesce: bool = Form(False),
    scan_interval_minutes: int = Form(...),
    scan_retry_attempts: int = Form(...),
    scan_retry_delay_seconds: float = Form(...),
    scan_max_instances: int = Form(...),
    scan_coalesce: bool = Form(False),
    history_poll_interval_minutes: int = Form(...),
    history_poll_retry_attempts: int = Form(...),
    history_poll_retry_delay_seconds: float = Form(...),
    history_poll_max_instances: int = Form(...),
    history_poll_coalesce: bool = Form(False),
) -> dict:
    return {
        "sync_interval_minutes": sync_interval_minutes,
        "sync_retry_attempts": sync_retry_attempts,
        "sync_retry_delay_seconds": sync_retry_delay_seconds,
        "sync_max_instances": sync_max_instances,
        "sync_coalesce": sync_coalesce,
        "scan_interval_minutes": scan_interval_minutes,
        "scan_retry_attempts": scan_retry_attempts,
        "scan_retry_delay_seconds": scan_retry_delay_seconds,
        "scan_max_instances": scan_max_instances,
        "scan_coalesce": scan_coalesce,
        "history_poll_interval_minutes": history_poll_interval_minutes,
        "history_poll_retry_attempts": history_poll_retry_attempts,
        "history_poll_retry_delay_seconds": history_poll_retry_delay_seconds,
        "history_poll_max_instances": history_poll_max_instances,
        "history_poll_coalesce": history_poll_coalesce,
    }


@router.get("/")
async def show_task_settings(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    task_settings = await service.get_task_settings(client)
    return templates.TemplateResponse(request, "tasks.html", {"settings": task_settings})


@router.post("/")
async def save_task_settings(
    request: Request,
    data: dict = Depends(_task_settings_form),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.update_task_settings(client, data)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "tasks.html",
            {"settings": data, "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    toast = urlencode(
        {
            "toast": translate(current_locale.get(), "settings.tasks.saved_toast"),
            "toast_type": "success",
        }
    )
    return RedirectResponse(f"/settings/tasks/?{toast}", status_code=303)


general_router = APIRouter(prefix="/settings/general")


@general_router.get("/")
async def show_general_settings(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    general_settings = await service.get_general_settings(client)
    webhook_settings = await service.get_webhook_settings(client)
    auth_settings = await service.get_auth_settings(client)
    return templates.TemplateResponse(
        request,
        "general.html",
        {
            "settings": general_settings,
            "locales": SUPPORTED_UI_LOCALES,
            "public_url": webhook_settings["public_url"],
            "auth_settings": auth_settings,
        },
    )


@general_router.post("/")
async def save_general_settings(
    request: Request,
    ui_locale: str = Form(...),
    public_url: str = Form(""),
    enabled: bool = Form(False),
    username: str = Form(""),
    password: str = Form(""),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    data = {"ui_locale": ui_locale}
    try:
        await service.update_general_settings(client, data)
        await service.update_webhook_settings(client, {"public_url": public_url})
        await service.update_auth_settings(
            client, {"enabled": enabled, "username": username, "password": password}
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        current_auth = await service.get_auth_settings(client)
        return templates.TemplateResponse(
            request,
            "general.html",
            {
                "settings": data,
                "locales": SUPPORTED_UI_LOCALES,
                "public_url": public_url,
                "auth_settings": {**current_auth, "enabled": enabled, "username": username},
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    # Use the newly-saved locale, not current_locale.get() — this is the one page where
    # the two can differ within the same request (resolve_locale ran before the save).
    toast = urlencode(
        {
            "toast": translate(ui_locale, "settings.general.saved_toast"),
            "toast_type": "success",
        }
    )
    return RedirectResponse(f"/settings/general/?{toast}", status_code=303)


@general_router.post("/api-key/regenerate")
async def regenerate_auth_api_key(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    auth_settings = await service.regenerate_api_key(client)
    return templates.TemplateResponse(
        request, "_api_key_field.html", {"auth_settings": auth_settings}
    )
