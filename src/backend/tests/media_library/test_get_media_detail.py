from datetime import UTC, datetime

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.get_media_detail import get_movie_detail, get_series_detail
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


def _seed_arr_service(session, service_type: str) -> ArrService:
    arr_service = ArrService(
        name=service_type, service_type=service_type, host="h", port=1, api_key="k"
    )
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    return arr_service


def test_get_movie_detail_returns_none_when_missing(in_memory_session):
    assert get_movie_detail(in_memory_session, 1) is None


def test_get_movie_detail_includes_files_subtitles_and_profile(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    assert arr_service.id is not None
    in_memory_session.add(
        LanguageProfile(
            name="Default",
            source_languages="en",
            target_languages="pt-BR,fr",
            is_default=True,
        )
    )
    movie = Movie(
        arr_service_id=arr_service.id,
        arr_id=1,
        title="Foo",
        remote_path="/movies/Foo",
        monitored=True,
        status="released",
    )
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    assert movie.id is not None
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=100, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    in_memory_session.refresh(media_file)
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo.en.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    detail = get_movie_detail(in_memory_session, movie.id)

    assert detail is not None
    assert detail.title == "Foo"
    assert detail.language_profile_name == "Default"
    assert detail.target_languages == ["pt-BR", "fr"]
    assert len(detail.files) == 1
    assert detail.files[0].relative_path == "Foo.mkv"
    assert detail.files[0].subtitles[0].language == "en"
    assert detail.files[0].subtitles[0].origin == "external"
    assert detail.files[0].missing_languages == ["pt-BR", "fr"]
    assert detail.missing_subtitles_count == 1


def test_get_movie_detail_uses_item_override_profile_over_default(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    assert arr_service.id is not None
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="pt-BR", is_default=True
        )
    )
    override_profile = LanguageProfile(name="Anime", source_languages="ja", target_languages="en")
    in_memory_session.add(override_profile)
    in_memory_session.commit()
    in_memory_session.refresh(override_profile)
    movie = Movie(
        arr_service_id=arr_service.id,
        arr_id=1,
        title="Foo",
        remote_path="/movies/Foo",
        language_profile_id=override_profile.id,
    )
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    assert movie.id is not None

    detail = get_movie_detail(in_memory_session, movie.id)

    assert detail is not None
    assert detail.language_profile_name == "Anime"
    assert detail.target_languages == ["en"]


def test_get_movie_detail_counts_files_without_subtitles_as_missing(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    assert arr_service.id is not None
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="en", is_default=True
        )
    )
    movie = Movie(arr_service_id=arr_service.id, arr_id=1, title="Foo", remote_path="/p")
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    assert movie.id is not None
    in_memory_session.add(
        MediaFile(
            movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
        )
    )
    in_memory_session.commit()

    detail = get_movie_detail(in_memory_session, movie.id)

    assert detail is not None
    assert detail.missing_subtitles_count == 1


def test_get_movie_detail_missing_count_is_zero_without_a_language_profile(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    assert arr_service.id is not None
    movie = Movie(arr_service_id=arr_service.id, arr_id=1, title="Foo", remote_path="/p")
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    assert movie.id is not None
    in_memory_session.add(
        MediaFile(
            movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
        )
    )
    in_memory_session.commit()

    detail = get_movie_detail(in_memory_session, movie.id)

    assert detail is not None
    assert detail.language_profile_name is None
    assert detail.missing_subtitles_count == 0


def test_get_series_detail_returns_none_when_missing(in_memory_session):
    assert get_series_detail(in_memory_session, 1) is None


def test_get_series_detail_matches_episodes_to_media_files(in_memory_session, monkeypatch):
    arr_service = _seed_arr_service(in_memory_session, "sonarr")
    assert arr_service.id is not None
    series = Series(
        arr_service_id=arr_service.id,
        arr_id=7,
        title="Bar",
        remote_path="/tv/Bar",
        monitored=True,
        status="continuing",
        episode_count=2,
        episode_file_count=1,
    )
    in_memory_session.add(series)
    in_memory_session.commit()
    in_memory_session.refresh(series)
    assert series.id is not None
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Season 01/Bar.S01E01.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    in_memory_session.refresh(media_file)
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-BR",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Season 01/Bar.S01E01.pt-BR.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    class _FakeClient:
        def list_episodes(self, series_id):
            assert series_id == 7
            return [
                EpisodeItem(
                    season_number=1,
                    episode_number=1,
                    title="Pilot",
                    relative_path="Season 01/Bar.S01E01.mkv",
                ),
                EpisodeItem(season_number=1, episode_number=2, title="TBA", relative_path=None),
            ]

        def close(self):
            pass

    monkeypatch.setattr(
        "legendarr_backend.media_library.get_media_detail.build_client",
        lambda arr_service: _FakeClient(),
    )

    detail = get_series_detail(in_memory_session, series.id)

    assert detail is not None
    assert len(detail.episodes) == 2
    assert detail.episodes[0].title == "Pilot"
    assert detail.episodes[0].media_file is not None
    assert detail.episodes[0].media_file.subtitles[0].language == "pt-BR"
    assert detail.episodes[1].media_file is None
    assert detail.missing_subtitles_count == 0
    assert detail.episodes_unavailable is False


def test_get_series_detail_degrades_when_sonarr_is_unreachable(in_memory_session, monkeypatch):
    arr_service = _seed_arr_service(in_memory_session, "sonarr")
    assert arr_service.id is not None
    series = Series(
        arr_service_id=arr_service.id,
        arr_id=7,
        title="Bar",
        remote_path="/tv/Bar",
    )
    in_memory_session.add(series)
    in_memory_session.commit()
    in_memory_session.refresh(series)
    assert series.id is not None

    class _FailingClient:
        def list_episodes(self, series_id):
            raise ProviderClientError("sonarr request timed out")

        def close(self):
            pass

    monkeypatch.setattr(
        "legendarr_backend.media_library.get_media_detail.build_client",
        lambda arr_service: _FailingClient(),
    )

    detail = get_series_detail(in_memory_session, series.id)

    assert detail is not None
    assert detail.episodes == []
    assert detail.episodes_unavailable is True
