from fastapi import APIRouter, Request
from legendarr_backend.language_profiles.manage_language_profile import list_language_profiles
from legendarr_backend.shared_kernel.database import get_session

from legendarr_web.shared_kernel.templates import get_templates

router = APIRouter(prefix="/language-profiles")
templates = get_templates("language_profiles")


@router.get("/")
def show_language_profiles(request: Request):
    with get_session() as session:
        profiles = list_language_profiles(session)
    return templates.TemplateResponse(
        request,
        "language_profiles.html",
        {"profiles": profiles},
    )
