import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from legendarr_web.authentication import service
from legendarr_web.authentication.cookies import SESSION_COOKIE_NAME
from legendarr_web.backend_client.client import error_detail, get_backend_client
from legendarr_web.templates.loader import get_templates

router = APIRouter()
templates = get_templates("authentication")

# `SESSION_TTL` on the backend is 30 days sliding — the cookie's own max_age just needs
# to outlive that, so an idle-but-not-yet-expired session's cookie isn't dropped first.
_COOKIE_MAX_AGE_SECONDS = 31 * 24 * 60 * 60


def _safe_next(next_path: str) -> str:
    """Only ever redirect somewhere inside this app — `next_path` comes from a query
    string / hidden form field, so a `//evil.example.com` value must never be honored."""
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return "/"


@router.get("/login")
async def show_login(request: Request, next: str = "/"):
    return templates.TemplateResponse(
        request, "login.html", {"next": _safe_next(next), "error": None}
    )


@router.post("/login")
async def submit_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    next_path = _safe_next(next)
    try:
        result = await service.login(
            client,
            username,
            password,
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise
        return templates.TemplateResponse(
            request,
            "login.html",
            {"next": next_path, "error": error_detail(exc)},
            status_code=exc.response.status_code,
        )
    response = RedirectResponse(next_path, status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        result["token"],
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout(request: Request, client: httpx.AsyncClient = Depends(get_backend_client)):
    await service.logout(client, request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
