from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_acquisition import search_context as search_context_module
from legendarr_backend.subtitle_acquisition.describe_search_resource import (
    describe_subtitle_search_resource,
)


def _movie(session, tmp_path: Path, **overrides) -> Movie:
    service = create_arr_service(
        session,
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
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo Bar",
        "remote_path": "/remote/Foo",
        "imdb_id": "tt1234567",
    }
    data.update(overrides)
    movie = Movie(**data)
    session.add(movie)
    session.commit()
    return movie


def _series(session, tmp_path: Path, **overrides) -> Series:
    service = create_arr_service(
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
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo Bar",
        "remote_path": "/remote/Foo",
    }
    data.update(overrides)
    series = Series(**data)
    session.add(series)
    session.commit()
    return series


def _write_video(tmp_path: Path, name: str) -> Path:
    video = tmp_path / "Foo" / name
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    return video


def test_describe_search_resource_for_a_movie(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/video.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    video = _write_video(tmp_path, "Foo.Bar.2024.1080p.WEB-DL.x264-GROUP.mkv")

    resource = describe_subtitle_search_resource(in_memory_session, media_file, video)

    assert resource.path == str(video)
    assert resource.release_name == "Foo.Bar.1080p.WEB-DL.X264-GROUP"


def test_describe_search_resource_for_a_series_episode(in_memory_session, tmp_path, monkeypatch):
    series = _series(in_memory_session, tmp_path)
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Foo/video.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    video = _write_video(tmp_path, "Foo.Bar.720p.HDTV.mkv")
    monkeypatch.setattr(
        search_context_module,
        "resolve_media_file_episode",
        lambda session, media_file: EpisodeItem(
            season_number=1, episode_number=2, title="Foo Bar", relative_path="Foo/video.mkv"
        ),
    )

    resource = describe_subtitle_search_resource(in_memory_session, media_file, video)

    assert resource.release_name == "Foo.Bar.S01E02.720p.HDTV"


def test_describe_search_resource_omits_unrecognized_attributes(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/video.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    video = _write_video(tmp_path, "video.mkv")

    resource = describe_subtitle_search_resource(in_memory_session, media_file, video)

    assert resource.release_name == "Foo.Bar"


def test_describe_search_resource_recovers_audio_and_dv_and_a_bracket_group(
    in_memory_session, tmp_path, monkeypatch
):
    """A Sonarr-renamed filename buries its release group after several bracket tags
    rather than right after the last recognized attribute — this module's own group
    pattern (unlike release_attributes.py's) still finds it, and also recovers the
    audio codec/channels and the Dolby Vision flag from those brackets."""
    series = _series(in_memory_session, tmp_path)
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Foo/video.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    video = _write_video(
        tmp_path,
        "Foo Bar (2023) - S01E03 - Part Three [WEBDL-2160p][DV][EAC3 Atmos 5.1]-NTb.mkv",
    )
    monkeypatch.setattr(
        search_context_module,
        "resolve_media_file_episode",
        lambda session, media_file: EpisodeItem(
            season_number=1, episode_number=3, title="Foo Bar", relative_path="Foo/video.mkv"
        ),
    )

    resource = describe_subtitle_search_resource(in_memory_session, media_file, video)

    assert resource.release_name == "Foo.Bar.S01E03.2160p.WEBDL.DDP5.1.DV-NTb"
