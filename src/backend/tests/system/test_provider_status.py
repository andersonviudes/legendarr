from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.circuit_breaker import (
    FAILURE_THRESHOLD,
    BreakerCategory,
    record_failure,
)
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation.models import TranslationAttempt
from legendarr_backend.system.provider_status import list_provider_health


def _movie(session, tmp_path, **overrides) -> Movie:
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
    data = {"arr_service_id": service.id, "arr_id": 1, "title": "Foo", "remote_path": "/remote/Foo"}
    data.update(overrides)
    movie = Movie(**data)
    session.add(movie)
    session.commit()
    return movie


def _media_file(session, movie: Movie) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo/Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    session.add(media_file)
    session.commit()
    return media_file


def _subtitle(session, media_file: MediaFile, language: str) -> Subtitle:
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language=language,
        origin=SubtitleOrigin.EXTERNAL,
        relative_path=f"Foo/Foo.{language}.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    session.add(subtitle)
    session.commit()
    return subtitle


def _entry(entries, category: str, kind: str):
    return next(entry for entry in entries if entry.category == category and entry.kind == kind)


def test_list_provider_health_defaults_every_provider_to_closed_with_no_success(in_memory_session):
    entries = list_provider_health(in_memory_session)

    deepl = _entry(entries, "translation", "deepl")
    assert deepl.circuit_open is False
    assert deepl.consecutive_failures == 0
    assert deepl.opened_at is None
    assert deepl.last_success_at is None

    opensubtitles = _entry(entries, "acquisition", "opensubtitles")
    assert opensubtitles.circuit_open is False
    assert opensubtitles.last_success_at is None


def test_list_provider_health_reports_last_translation_success(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    subtitle = _subtitle(in_memory_session, media_file, "pt-br")
    assert subtitle.id is not None
    now = datetime.now(UTC)
    in_memory_session.add(
        TranslationAttempt(
            subtitle_id=subtitle.id,
            provider="deepl",
            source_language="en",
            target_language="pt-BR",
            translated_at=now,
        )
    )
    in_memory_session.commit()

    entries = list_provider_health(in_memory_session)

    last_success_at = _entry(entries, "translation", "deepl").last_success_at
    assert last_success_at is not None
    assert last_success_at.replace(tzinfo=None) == now.replace(tzinfo=None)


def test_list_provider_health_reports_last_acquisition_success(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    subtitle = _subtitle(in_memory_session, media_file, "en")
    assert subtitle.id is not None
    now = datetime.now(UTC)
    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle.id,
            provider="opensubtitles",
            release_name="Foo.WEB-DL",
            download_id="1",
            score=0.9,
            title_similarity=0.9,
            attempted_at=now,
        )
    )
    in_memory_session.commit()

    entries = list_provider_health(in_memory_session)

    last_success_at = _entry(entries, "acquisition", "opensubtitles").last_success_at
    assert last_success_at is not None
    assert last_success_at.replace(tzinfo=None) == now.replace(tzinfo=None)


def test_list_provider_health_reports_an_open_circuit(in_memory_session, isolated_circuit_breakers):
    for _ in range(FAILURE_THRESHOLD):
        record_failure(BreakerCategory.ACQUISITION, "subdl")

    entries = list_provider_health(in_memory_session)

    subdl = _entry(entries, "acquisition", "subdl")
    assert subdl.circuit_open is True
    assert subdl.consecutive_failures == FAILURE_THRESHOLD
    assert subdl.opened_at is not None
