from collections.abc import Iterator
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.language_profiles.manage_language_profile import (
    create_language_profile,
    delete_language_profile,
    get_language_profile,
    list_language_profiles,
    update_language_profile,
)
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.schemas import LanguageProfileInput

router = APIRouter(prefix="/language-profiles")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _raise_duplicate_name(session: Session, exc: IntegrityError) -> NoReturn:
    session.rollback()
    raise HTTPException(
        status_code=409, detail="A language profile with this name already exists"
    ) from exc


@router.get("/", response_model=list[LanguageProfile])
def list_profiles(session: Session = Depends(_get_session)) -> list[LanguageProfile]:
    return list_language_profiles(session)


@router.post("/", response_model=LanguageProfile, status_code=201)
def create_profile(
    data: LanguageProfileInput, session: Session = Depends(_get_session)
) -> LanguageProfile:
    try:
        return create_language_profile(session, data)
    except IntegrityError as exc:
        _raise_duplicate_name(session, exc)


@router.get("/{profile_id}", response_model=LanguageProfile)
def get_profile(profile_id: int, session: Session = Depends(_get_session)) -> LanguageProfile:
    profile = get_language_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Language profile not found")
    return profile


@router.put("/{profile_id}", response_model=LanguageProfile)
def update_profile(
    profile_id: int, data: LanguageProfileInput, session: Session = Depends(_get_session)
) -> LanguageProfile:
    try:
        profile = update_language_profile(session, profile_id, data)
    except IntegrityError as exc:
        _raise_duplicate_name(session, exc)
    if profile is None:
        raise HTTPException(status_code=404, detail="Language profile not found")
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: int, session: Session = Depends(_get_session)) -> None:
    if not delete_language_profile(session, profile_id):
        raise HTTPException(status_code=404, detail="Language profile not found")
