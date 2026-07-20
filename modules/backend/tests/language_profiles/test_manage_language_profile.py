from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.manage_language_profile import (
    create_language_profile,
    delete_language_profile,
    get_language_profile,
    list_language_profiles,
    update_language_profile,
)
from legendarr_backend.language_profiles.schemas import LanguageProfileInput
from legendarr_backend.media_library.models import Movie
from sqlmodel import select


def _profile_input(**overrides) -> LanguageProfileInput:
    data = {
        "name": "anime",
        "source_languages": "ja",
        "target_languages": "pt-BR,en",
    }
    data.update(overrides)
    return LanguageProfileInput(**data)


def test_create_and_list_language_profile(in_memory_session):
    create_language_profile(in_memory_session, _profile_input())

    profiles = list_language_profiles(in_memory_session)

    assert [profile.name for profile in profiles] == ["anime"]


def test_get_language_profile_returns_none_when_missing(in_memory_session):
    assert get_language_profile(in_memory_session, 1) is None


def test_update_language_profile_replaces_fields(in_memory_session):
    profile = create_language_profile(in_memory_session, _profile_input())

    updated = update_language_profile(
        in_memory_session,
        profile.id,
        _profile_input(target_languages="pt-BR", forced=True, hearing_impaired=True),
    )

    assert updated.target_languages == "pt-BR"
    assert updated.forced is True
    assert updated.hearing_impaired is True


def test_update_language_profile_returns_none_when_missing(in_memory_session):
    assert update_language_profile(in_memory_session, 1, _profile_input()) is None


def test_delete_language_profile(in_memory_session):
    profile = create_language_profile(in_memory_session, _profile_input())

    assert delete_language_profile(in_memory_session, profile.id) is True
    assert list_language_profiles(in_memory_session) == []


def test_delete_language_profile_returns_false_when_missing(in_memory_session):
    assert delete_language_profile(in_memory_session, 1) is False


def test_delete_language_profile_clears_override_on_pinned_media(in_memory_session):
    arr_service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr", service_type="radarr", host="radarr", port=7878, api_key="key"
        ),
    )
    profile = create_language_profile(in_memory_session, _profile_input())
    in_memory_session.add(
        Movie(
            arr_service_id=arr_service.id,
            arr_id=1,
            title="A",
            remote_path="/movies/A",
            language_profile_id=profile.id,
        )
    )
    in_memory_session.commit()

    assert delete_language_profile(in_memory_session, profile.id) is True

    movie = in_memory_session.exec(select(Movie)).one()
    assert movie.language_profile_id is None
