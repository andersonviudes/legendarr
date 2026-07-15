from legendarr_backend.language_profiles.manage_language_profile import (
    create_language_profile,
    list_language_profiles,
)
from legendarr_backend.language_profiles.models import LanguageProfile
from sqlmodel import Session, SQLModel, create_engine


def test_create_and_list_language_profile():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        create_language_profile(
            session,
            LanguageProfile(
                name="anime",
                source_languages="ja",
                target_languages="pt-BR,en",
            ),
        )

        profiles = list_language_profiles(session)

    assert [profile.name for profile in profiles] == ["anime"]
