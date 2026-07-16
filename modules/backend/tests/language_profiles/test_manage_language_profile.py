from legendarr_backend.language_profiles.manage_language_profile import (
    create_language_profile,
    list_language_profiles,
)
from legendarr_backend.language_profiles.models import LanguageProfile


def test_create_and_list_language_profile(in_memory_session):
    create_language_profile(
        in_memory_session,
        LanguageProfile(
            name="anime",
            source_languages="ja",
            target_languages="pt-BR,en",
        ),
    )

    profiles = list_language_profiles(in_memory_session)

    assert [profile.name for profile in profiles] == ["anime"]
