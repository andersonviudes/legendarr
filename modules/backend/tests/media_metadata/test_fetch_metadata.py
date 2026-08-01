from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.media_library.models import Movie
from legendarr_backend.media_metadata import fetch_metadata
from legendarr_backend.media_metadata.manage_metadata_provider import (
    ensure_metadata_providers_seeded,
    list_metadata_providers,
    update_metadata_provider,
)
from legendarr_backend.media_metadata.models import MediaMetadata
from legendarr_backend.media_metadata.providers.base import MetadataResult
from legendarr_backend.media_metadata.schemas import MetadataProviderConfigInput
from sqlmodel import select


class _StubProvider:
    def __init__(self, result: MetadataResult | None) -> None:
        self._result = result

    def fetch(self, **kwargs) -> MetadataResult | None:
        return self._result

    def close(self) -> None:
        pass


class _FailingProvider:
    def fetch(self, **kwargs) -> MetadataResult | None:
        raise RuntimeError("boom")

    def close(self) -> None:
        pass


def _seed_movie(session) -> Movie:
    arr_service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    movie = Movie(
        arr_service_id=arr_service.id,
        arr_id=1,
        title="A Movie",
        remote_path="/p",
        imdb_id="tt1",
    )
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def _configure_all_providers(session) -> None:
    ensure_metadata_providers_seeded(session)
    for provider in list_metadata_providers(session):
        update_metadata_provider(session, provider.id, MetadataProviderConfigInput(api_key="key"))


def test_fetch_metadata_for_new_items_is_a_noop_with_nothing_to_fetch(in_memory_session):
    fetch_metadata.fetch_metadata_for_new_items(in_memory_session, movies=[], series=[])

    assert in_memory_session.exec(select(MediaMetadata)).all() == []


def test_fetch_metadata_for_new_items_merges_tvdb_and_imdb_by_policy(
    in_memory_session, monkeypatch
):
    session = in_memory_session
    _configure_all_providers(session)
    movie = _seed_movie(session)

    def _fake_build(config):
        if config.kind == "tvdb":
            return _StubProvider(
                MetadataResult(overview="TVDB overview", poster_url="tvdb.png", year=1994)
            )
        return _StubProvider(MetadataResult(overview="IMDb overview", imdb_rating=9.3))

    monkeypatch.setattr(fetch_metadata, "build_metadata_provider", _fake_build)

    fetch_metadata.fetch_metadata_for_new_items(session, movies=[movie], series=[])

    stored = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie.id)).one()
    # TheTVDB wins overview/poster/year; IMDb only ever contributes the rating.
    assert stored.overview == "TVDB overview"
    assert stored.poster_url == "tvdb.png"
    assert stored.year == 1994
    assert stored.imdb_rating == 9.3


def test_fetch_metadata_for_new_items_skips_unconfigured_providers(in_memory_session, monkeypatch):
    session = in_memory_session
    ensure_metadata_providers_seeded(session)  # seeded enabled, but no api_key set yet
    movie = _seed_movie(session)
    called: list[str] = []
    monkeypatch.setattr(
        fetch_metadata, "build_metadata_provider", lambda config: called.append(config.kind)
    )

    fetch_metadata.fetch_metadata_for_new_items(session, movies=[movie], series=[])

    assert called == []
    assert session.exec(select(MediaMetadata)).all() == []


def test_fetch_metadata_for_new_items_survives_a_failing_provider(in_memory_session, monkeypatch):
    session = in_memory_session
    _configure_all_providers(session)
    movie = _seed_movie(session)

    def _fake_build(config):
        if config.kind == "tvdb":
            return _FailingProvider()
        return _StubProvider(MetadataResult(imdb_rating=8.0))

    monkeypatch.setattr(fetch_metadata, "build_metadata_provider", _fake_build)

    fetch_metadata.fetch_metadata_for_new_items(session, movies=[movie], series=[])

    stored = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie.id)).one()
    assert stored.overview is None
    assert stored.imdb_rating == 8.0


def test_fetch_metadata_for_new_items_leaves_no_row_when_nothing_usable(
    in_memory_session, monkeypatch
):
    session = in_memory_session
    _configure_all_providers(session)
    movie = _seed_movie(session)
    monkeypatch.setattr(
        fetch_metadata, "build_metadata_provider", lambda config: _StubProvider(None)
    )

    fetch_metadata.fetch_metadata_for_new_items(session, movies=[movie], series=[])

    assert session.exec(select(MediaMetadata)).all() == []
