from fastapi import APIRouter, Request

from legendarr_web.shared_kernel.templates.loader import get_templates

router = APIRouter(prefix="/history")
templates = get_templates("history")


@router.get("/")
def show_history(request: Request):
    return templates.TemplateResponse(request, "history.html", {})
