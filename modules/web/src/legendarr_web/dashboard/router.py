from fastapi import APIRouter, Request

from legendarr_web.shared_kernel.templates import get_templates

router = APIRouter()
templates = get_templates("dashboard")


@router.get("/")
def show_dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"title": "legendarr"},
    )
