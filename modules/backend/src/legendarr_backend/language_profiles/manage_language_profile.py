from sqlmodel import Session, select, update

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.schemas import LanguageProfileInput
from legendarr_backend.media_library.models import Movie, Series


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
    # SQLite runs with FK enforcement off by default, so the database won't cascade for
    # us — clear the per-item override on any Movie/Series pinned to this profile instead
    # of leaving it pointing at a deleted row.
    for model in (Movie, Series):
        session.exec(
            update(model)
            .where(model.language_profile_id == profile_id)
            .values(language_profile_id=None)
        )
    session.delete(profile)
    session.commit()
    return True
