from datetime import UTC, datetime

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.list_wanted_media import list_wanted_media
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


def test_list_wanted_media_returns_empty_list_with_nothing_missing(in_memory_session):
    assert list_wanted_media(in_memory_session) == []


def test_list_wanted_media_includes_movie_missing_a_target_language(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "radarr")
    assert arr_service.id is not None
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="pt-BR", is_default=True
        )
    )
    movie = Movie(arr_service_id=arr_service.id, arr_id=1, title="Foo", remote_path="/p")
    in_memory_session.add(movie)
    in_memory_session.commit()
    in_memory_session.refresh(movie)
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()

    wanted = list_wanted_media(in_memory_session)

    assert len(wanted) == 1
    assert wanted[0].id == movie.id
    assert wanted[0].kind == "movie"
    assert wanted[0].title == "Foo"
    assert wanted[0].missing_languages == ["pt-BR"]
    assert wanted[0].missing_files_count == 1


def test_list_wanted_media_excludes_movie_with_every_target_language(in_memory_session):
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
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
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

    assert list_wanted_media(in_memory_session) == []


def test_list_wanted_media_series_counts_only_the_episode_still_missing(in_memory_session):
    arr_service = _seed_arr_service(in_memory_session, "sonarr")
    assert arr_service.id is not None
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="pt-BR", is_default=True
        )
    )
    series = Series(arr_service_id=arr_service.id, arr_id=7, title="Bar", remote_path="/tv/Bar")
    in_memory_session.add(series)
    in_memory_session.commit()
    in_memory_session.refresh(series)
    covered = MediaFile(
        series_id=series.id,
        relative_path="Bar.S01E01.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    missing = MediaFile(
        series_id=series.id,
        relative_path="Bar.S01E02.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(covered)
    in_memory_session.add(missing)
    in_memory_session.commit()
    in_memory_session.refresh(covered)
    assert covered.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=covered.id,
            language="pt-br",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Bar.S01E01.pt-br.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    wanted = list_wanted_media(in_memory_session)

    assert len(wanted) == 1
    assert wanted[0].kind == "series"
    assert wanted[0].missing_languages == ["pt-BR"]
    assert wanted[0].missing_files_count == 1
