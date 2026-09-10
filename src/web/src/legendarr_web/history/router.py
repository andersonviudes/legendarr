import math

import httpx
from fastapi import APIRouter, Depends, Request

from legendarr_web.backend_client.client import get_backend_client
from legendarr_web.history import service
from legendarr_web.templates.loader import get_templates

router = APIRouter(prefix="/history")
templates = get_templates("history")

# Mirrors the backend's `history.list_history.DEFAULT_PAGE_SIZE` — kept as its own
# constant rather than imported, since `legendarr_web` never imports `legendarr_backend`
# directly (see AGENTS.md's architecture section), only calls its HTTP API.
PAGE_SIZE = 25


@router.get("/")
async def show_history(
    request: Request,
    q: str = "",
    page: int = 1,
    client: httpx.AsyncClient = Depends(get_backend_client),
):
    page_result = await service.get_history(client, q=q, page=page, page_size=PAGE_SIZE)
    total_pages = max(1, math.ceil(page_result["total"] / PAGE_SIZE))
    context = {
        "entries": page_result["entries"],
        "q": q,
        "page": page_result["page"],
        "total_pages": total_pages,
    }
    template_name = (
        "_history_results.html" if request.headers.get("HX-Request") == "true" else "history.html"
    )
    return templates.TemplateResponse(request, template_name, context)
