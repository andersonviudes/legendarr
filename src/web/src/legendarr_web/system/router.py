from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.system import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/system")
templates = get_templates("system")


@router.get("/")
async def show_system(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    lines = await service.get_recent_logs(client)
    return templates.TemplateResponse(request, "system.html", {"lines": lines})


@router.get("/logs")
async def get_logs(
    request: Request,
    level: str = "",
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    lines = await service.get_recent_logs(client, level or None)
    return templates.TemplateResponse(request, "_log_lines.html", {"lines": lines})


@router.get("/tasks/")
async def show_tasks(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    tasks = await service.get_running_tasks(client)
    return templates.TemplateResponse(request, "tasks.html", {"tasks": tasks})


@router.get("/tasks/running")
async def get_running_tasks_partial(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    tasks = await service.get_running_tasks(client)
    return templates.TemplateResponse(request, "_running_tasks_list.html", {"tasks": tasks})


@router.get("/tasks/count")
async def get_running_tasks_count(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    tasks = await service.get_running_tasks(client)
    return templates.TemplateResponse(
        request, "_running_tasks_indicator.html", {"count": len(tasks)}
    )


@router.get("/sessions/")
async def show_sessions(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    sessions = await service.get_sessions(client)
    current_session = request.state.auth_session
    current_session_id = current_session["id"] if current_session else None
    return templates.TemplateResponse(
        request,
        "sessions.html",
        {"sessions": sessions, "current_session_id": current_session_id},
    )


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: int, client: httpx.AsyncClient = Depends(get_backend_client)):
    try:
        await service.revoke_session(client, session_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
    toast = urlencode({"toast": "Session revoked.", "toast_type": "success"})
    return RedirectResponse(f"/system/sessions/?{toast}", status_code=303)


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(
    request: Request, client: httpx.AsyncClient = Depends(get_backend_client)
):
    current_session = request.state.auth_session
    if current_session is not None:
        await service.revoke_other_sessions(client, current_session["id"])
    toast = urlencode({"toast": "Other sessions revoked.", "toast_type": "success"})
    return RedirectResponse(f"/system/sessions/?{toast}", status_code=303)


@router.get("/directories/browse")
async def browse_directories(
    request: Request,
    target: str,
    path: str = "/",
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    try:
        listing = await service.browse_directory(client, path)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "_directory_browser.html",
            {
                "current_path": None,
                "breadcrumbs": [],
                "directories": [],
                "target": target,
                "error": error_detail(exc),
            },
            status_code=exc.response.status_code,
        )
    return templates.TemplateResponse(
        request,
        "_directory_browser.html",
        {
            "current_path": listing["path"],
            "breadcrumbs": _breadcrumbs(listing["path"]),
            "directories": _directory_rows(listing["path"], listing["directories"]),
            "target": target,
        },
    )


def _breadcrumbs(path: str) -> list[dict[str, str]]:
    """Turn an absolute path into clickable segments, root first."""
    segments = [segment for segment in path.split("/") if segment]
    breadcrumbs = [{"name": "/", "path": "/"}]
    current = ""
    for segment in segments:
        current += f"/{segment}"
        breadcrumbs.append({"name": segment, "path": current})
    return breadcrumbs


def _directory_rows(base_path: str, names: list[str]) -> list[dict[str, str]]:
    """Pair each subdirectory name with its full path, for the browser's row links."""
    return [{"name": name, "path": f"{base_path.rstrip('/')}/{name}"} for name in names]
