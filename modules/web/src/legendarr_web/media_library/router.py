from fastapi import APIRouter, Request

from legendarr_web.shared_kernel.templates.loader import get_templates

router = APIRouter(prefix="/media")
templates = get_templates("media_library")


@router.get("/movies")
def show_movies(request: Request):
    return templates.TemplateResponse(request, "movies.html", {"movies": []})


@router.get("/series")
def show_series(request: Request):
    return templates.TemplateResponse(request, "series.html", {"series": []})
