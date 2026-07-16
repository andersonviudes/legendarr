from collections.abc import Iterator

from fastapi import APIRouter, Depends
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.language_profiles.manage_language_profile import list_language_profiles
from legendarr_backend.language_profiles.models import LanguageProfile

router = APIRouter(prefix="/language-profiles")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("/", response_model=list[LanguageProfile])
def list_profiles(session: Session = Depends(_get_session)) -> list[LanguageProfile]:
    return list_language_profiles(session)
