from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.backup import service
from legendarr_web.i18n.translator import current_locale, translate
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/settings/backup")
templates = get_templates("backup")


def _toast_redirect(message_key: str) -> RedirectResponse:
    toast = urlencode(
        {"toast": translate(current_locale.get(), message_key), "toast_type": "success"}
    )
    return RedirectResponse(f"/settings/backup/?{toast}", status_code=303)


@router.get("/")
async def show_backups(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    backups = await service.list_backups(client)
    retention = await service.get_backup_settings(client)
    return templates.TemplateResponse(
        request, "backups.html", {"backups": backups, "retention": retention}
    )


@router.post("/")
async def create_backup(client: httpx.AsyncClient = Depends(get_backend_client)):
    await service.create_backup(client)
    return _toast_redirect("settings.backup.created_toast")


@router.post("/retention")
async def save_retention(
    request: Request,
    backup_retention_count: int = Form(...),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        await service.update_backup_settings(
            client, {"backup_retention_count": backup_retention_count}
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        backups = await service.list_backups(client)
        return templates.TemplateResponse(
            request,
            "backups.html",
            {
                "backups": backups,
                "retention": {"backup_retention_count": backup_retention_count},
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    return _toast_redirect("settings.backup.retention_saved_toast")


@router.get("/{filename}/download")
async def download_backup(filename: str, client: httpx.AsyncClient = Depends(get_backend_client)):
    try:
        response = await service.download_backup(client, filename)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Backup not found") from exc
        raise
    return Response(
        content=response.content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{filename}/delete")
async def delete_backup(
    request: Request, filename: str, client: httpx.AsyncClient = Depends(get_backend_client)
):
    try:
        await service.delete_backup(client, filename)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    toast = urlencode(
        {
            "toast": translate(current_locale.get(), "settings.backup.deleted_toast"),
            "toast_type": "success",
        }
    )
    redirect_url = f"/settings/backup/?{toast}"
    # The row's delete button is htmx-driven (for `hx-confirm`) rather than a plain form
    # submit, so an HTMX request needs `HX-Redirect` instead of a 303 it wouldn't follow
    # the same way — same posture as `app.py`'s login redirect.
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": redirect_url})
    return RedirectResponse(redirect_url, status_code=303)


@router.post("/restore")
async def restore(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's own multipart dependency idiom
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    content = await file.read()
    try:
        result = await service.restore_backup(client, file.filename or "backup.zip", content)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "_restore_result.html",
            {"error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    return templates.TemplateResponse(
        request, "_restore_result.html", {"message": result["message"]}
    )
