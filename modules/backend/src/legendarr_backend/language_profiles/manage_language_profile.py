from sqlmodel import Session, select

from legendarr_backend.language_profiles.models import LanguageProfile


def create_language_profile(session: Session, profile: LanguageProfile) -> LanguageProfile:
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_language_profiles(session: Session) -> list[LanguageProfile]:
    return list(session.exec(select(LanguageProfile)).all())
