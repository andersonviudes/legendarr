from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_effective_profile,
)
from legendarr_backend.media_library.models import Movie


def _seed_arr_service(session) -> ArrService:
    arr_service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    return arr_service


def _seed_movie(session, arr_service_id: int, **overrides) -> Movie:
    movie = Movie(
        arr_service_id=arr_service_id,
        arr_id=1,
        title="Foo",
        remote_path="/movies/Foo",
        **overrides,
    )
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def test_resolve_effective_profile_returns_none_when_no_profile_exists(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session)
    movie = _seed_movie(in_memory_session, arr_service.id)

    assert resolve_effective_profile(in_memory_session, movie) is None


def test_resolve_effective_profile_falls_back_to_default(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session)
    default_profile = LanguageProfile(
        name="Default", source_languages="en", target_languages="pt-BR", is_default=True
    )
    in_memory_session.add(default_profile)
    in_memory_session.commit()
    in_memory_session.refresh(default_profile)
    movie = _seed_movie(in_memory_session, arr_service.id)

    resolved = resolve_effective_profile(in_memory_session, movie)

    assert resolved is not None
    assert resolved.id == default_profile.id


def test_resolve_effective_profile_prefers_item_override_over_default(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session)
    default_profile = LanguageProfile(
        name="Default", source_languages="en", target_languages="pt-BR", is_default=True
    )
    override_profile = LanguageProfile(name="Anime", source_languages="ja", target_languages="en")
    in_memory_session.add(default_profile)
    in_memory_session.add(override_profile)
    in_memory_session.commit()
    in_memory_session.refresh(default_profile)
    in_memory_session.refresh(override_profile)
    movie = _seed_movie(in_memory_session, arr_service.id, language_profile_id=override_profile.id)

    resolved = resolve_effective_profile(in_memory_session, movie)

    assert resolved is not None
    assert resolved.id == override_profile.id
