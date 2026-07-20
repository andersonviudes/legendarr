from sqlmodel import Session, select

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.schemas import LanguageProfileInput


def create_language_profile(session: Session, data: LanguageProfileInput) -> LanguageProfile:
    profile = LanguageProfile.model_validate(data.model_dump())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_language_profiles(session: Session) -> list[LanguageProfile]:
    return list(session.exec(select(LanguageProfile)).all())


def get_language_profile(session: Session, profile_id: int) -> LanguageProfile | None:
    return session.get(LanguageProfile, profile_id)


def update_language_profile(
    session: Session, profile_id: int, data: LanguageProfileInput
) -> LanguageProfile | None:
    profile = session.get(LanguageProfile, profile_id)
    if profile is None:
        return None
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def delete_language_profile(session: Session, profile_id: int) -> bool:
    profile = session.get(LanguageProfile, profile_id)
    if profile is None:
        return False
    # The FK's ON DELETE SET NULL (enforced via PRAGMA foreign_keys=ON) clears the
    # per-item override on any Movie/Series pinned to this profile for us.
    session.delete(profile)
    session.commit()
    return True
