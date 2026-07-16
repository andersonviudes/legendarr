from fastapi import APIRouter, Request

from legendarr_web.shared_kernel.templates.loader import get_templates

router = APIRouter(prefix="/system")
templates = get_templates("system")


@router.get("/")
def show_system(request: Request):
    return templates.TemplateResponse(request, "system.html", {})
