from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.system.resolve_job_media_title import resolve_job_media_titles


def _radarr_service(session):
    return create_arr_service(
        session,
        ArrServiceInput(
            name="radarr", service_type="radarr", host="radarr", port=7878, api_key="k"
        ),
    )


def _sonarr_service(session):
    return create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr", service_type="sonarr", host="sonarr", port=8989, api_key="k"
        ),
    )


def _movie_media_file(session, *, title: str = "Foo") -> MediaFile:
    service = _radarr_service(session)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title=title, remote_path="/remote/Foo")
    session.add(movie)
    session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    session.add(media_file)
    session.commit()
    return media_file


def test_resolve_job_media_titles_resolves_a_subtitle_scan_job(in_memory_session):
    media_file = _movie_media_file(in_memory_session)
    assert media_file.id is not None

    titles = resolve_job_media_titles(in_memory_session, [f"subtitle_scan:{media_file.id}"])

    assert titles == {f"subtitle_scan:{media_file.id}": "Foo"}


def test_resolve_job_media_titles_resolves_acquisition_and_translation_jobs(in_memory_session):
    media_file = _movie_media_file(in_memory_session)
    assert media_file.id is not None

    titles = resolve_job_media_titles(
        in_memory_session,
        [f"subtitle_acquisition:{media_file.id}", f"subtitle_translation:{media_file.id}"],
    )

    assert titles == {
        f"subtitle_acquisition:{media_file.id}": "Foo",
        f"subtitle_translation:{media_file.id}": "Foo",
    }


def test_resolve_job_media_titles_resolves_a_timing_sync_job_via_its_subtitle(in_memory_session):
    media_file = _movie_media_file(in_memory_session)
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.en.srt",
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None

    titles = resolve_job_media_titles(in_memory_session, [f"subtitle_timing_sync:{subtitle.id}"])

    assert titles == {f"subtitle_timing_sync:{subtitle.id}": "Foo"}


def test_resolve_job_media_titles_resolves_a_pending_reconcile_job(in_memory_session):
    service = _sonarr_service(in_memory_session)
    assert service.id is not None
    series = Series(arr_service_id=service.id, arr_id=7, title="Bar", remote_path="/remote/Bar")
    in_memory_session.add(series)
    in_memory_session.commit()
    assert series.id is not None

    titles = resolve_job_media_titles(
        in_memory_session, [f"pending_subtitle_reconcile:{series.id}"]
    )

    assert titles == {f"pending_subtitle_reconcile:{series.id}": "Bar"}


def test_resolve_job_media_titles_resolves_media_scan_and_metadata_fetch_jobs(in_memory_session):
    radarr = _radarr_service(in_memory_session)
    assert radarr.id is not None
    movie = Movie(arr_service_id=radarr.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    sonarr = _sonarr_service(in_memory_session)
    assert sonarr.id is not None
    series = Series(arr_service_id=sonarr.id, arr_id=7, title="Bar", remote_path="/remote/Bar")
    in_memory_session.add(movie)
    in_memory_session.add(series)
    in_memory_session.commit()
    assert movie.id is not None
    assert series.id is not None

    titles = resolve_job_media_titles(
        in_memory_session,
        [
            f"media_scan:movie:{movie.id}",
            f"media_scan:series:{series.id}",
            f"media_metadata_fetch:movie:{movie.id}",
        ],
    )

    assert titles == {
        f"media_scan:movie:{movie.id}": "Foo",
        f"media_scan:series:{series.id}": "Bar",
        f"media_metadata_fetch:movie:{movie.id}": "Foo",
    }


def test_resolve_job_media_titles_omits_a_job_naming_deleted_media(in_memory_session):
    titles = resolve_job_media_titles(in_memory_session, ["subtitle_scan:999"])

    assert titles == {}


def test_resolve_job_media_titles_omits_a_fanout_jobs_own_descriptive_id(in_memory_session):
    titles = resolve_job_media_titles(
        in_memory_session, ["subtitle_discovery_scan_fanout", "media_library_sync"]
    )

    assert titles == {}
