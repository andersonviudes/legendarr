from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.media_library.locate import (
    resolve_media_file_episode,
    resolve_media_file_owner,
    resolve_media_file_path,
)
from legendarr_backend.media_library.models import MediaFile, Movie, Series


def test_resolve_media_file_path_applies_path_mapping(in_memory_session, tmp_path):
    service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()

    resolved = resolve_media_file_path(in_memory_session, media_file)

    assert resolved == Path(tmp_path) / "Foo" / "Foo.mkv"


def test_resolve_media_file_path_returns_none_when_owner_deleted(in_memory_session):
    media_file = MediaFile(
        movie_id=999, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )

    resolved = resolve_media_file_path(in_memory_session, media_file)

    assert resolved is None


def test_resolve_media_file_owner_returns_movie(in_memory_session):
    service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
        ),
    )
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )

    owner = resolve_media_file_owner(in_memory_session, media_file)

    assert owner == movie


def test_resolve_media_file_owner_returns_none_when_deleted(in_memory_session):
    media_file = MediaFile(
        movie_id=999, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )

    assert resolve_media_file_owner(in_memory_session, media_file) is None


def _sonarr_service(session, tmp_path):
    return create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr",
            service_type="sonarr",
            host="sonarr",
            port=8989,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )


def test_resolve_media_file_episode_returns_none_for_a_movie_file(in_memory_session):
    media_file = MediaFile(
        movie_id=999, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )

    assert resolve_media_file_episode(in_memory_session, media_file) is None


def test_resolve_media_file_episode_returns_none_when_series_deleted(in_memory_session):
    media_file = MediaFile(
        series_id=999,
        relative_path="Foo/Foo.S01E02.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )

    assert resolve_media_file_episode(in_memory_session, media_file) is None


def test_resolve_media_file_episode_matches_by_relative_path(
    in_memory_session, tmp_path, monkeypatch
):
    service = _sonarr_service(in_memory_session, tmp_path)
    assert service.id is not None
    series = Series(arr_service_id=service.id, arr_id=7, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(series)
    in_memory_session.commit()
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Foo/Foo.S01E02.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )

    class _FakeClient:
        def list_episodes(self, series_id):
            assert series_id == 7
            return [
                EpisodeItem(
                    season_number=1,
                    episode_number=1,
                    title="Pilot",
                    relative_path="Foo/Foo.S01E01.mkv",
                ),
                EpisodeItem(
                    season_number=1,
                    episode_number=2,
                    title="Second",
                    relative_path="Foo/Foo.S01E02.mkv",
                ),
            ]

        def close(self):
            pass

    monkeypatch.setattr(
        "legendarr_backend.media_library.locate.build_client",
        lambda arr_service: _FakeClient(),
    )

    episode = resolve_media_file_episode(in_memory_session, media_file)

    assert episode is not None
    assert episode.season_number == 1
    assert episode.episode_number == 2


def test_resolve_media_file_episode_returns_none_when_sonarr_unreachable(
    in_memory_session, tmp_path, monkeypatch
):
    service = _sonarr_service(in_memory_session, tmp_path)
    assert service.id is not None
    series = Series(arr_service_id=service.id, arr_id=7, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(series)
    in_memory_session.commit()
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Foo/Foo.S01E02.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )

    class _FailingClient:
        def list_episodes(self, series_id):
            raise ProviderClientError("sonarr request timed out")

        def close(self):
            pass

    monkeypatch.setattr(
        "legendarr_backend.media_library.locate.build_client",
        lambda arr_service: _FailingClient(),
    )

    assert resolve_media_file_episode(in_memory_session, media_file) is None
