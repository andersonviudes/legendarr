from fastapi import APIRouter, Request

from legendarr_web.shared_kernel.templates import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


@router.get("/")
def show_media_library(request: Request):
    return templates.TemplateResponse(
        request,
        "media_library.html",
        {"movies": [], "series": []},
    )
