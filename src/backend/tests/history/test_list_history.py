from datetime import UTC, datetime, timedelta

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.history.list_history import list_history
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt, AcquisitionFailure
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation.models import TranslationAttempt, TranslationFailure


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


def _media_file(session, *, movie: Movie | None = None, series: Series | None = None) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id if movie is not None else None,
        series_id=series.id if series is not None else None,
        relative_path="Foo/Foo.S01E01.mkv" if series is not None else "Foo/Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _series(session, tmp_path, **overrides) -> Series:
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
    data = {"arr_service_id": service.id, "arr_id": 1, "title": "Bar", "remote_path": "/remote/Bar"}
    data.update(overrides)
    series = Series(**data)
    session.add(series)
    session.commit()
    return series


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


def test_list_history_empty_state(in_memory_session):
    assert list_history(in_memory_session) == []


def test_list_history_includes_translation_success_and_failure(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie=movie)
    subtitle = _subtitle(in_memory_session, media_file, "pt-br")
    assert subtitle.id is not None
    assert media_file.id is not None

    in_memory_session.add(
        TranslationAttempt(
            subtitle_id=subtitle.id,
            provider="deepl",
            source_language="en",
            target_language="pt-BR",
            translated_at=datetime.now(UTC),
        )
    )
    in_memory_session.add(
        TranslationFailure(
            media_file_id=media_file.id,
            source_language="en",
            target_language="es",
            error_message="google: quota exceeded",
            failed_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    entries = list_history(in_memory_session)

    assert len(entries) == 2
    success = next(entry for entry in entries if entry.status == "success")
    assert success.category == "translation"
    assert success.media_title == "Foo"
    assert success.language == "pt-BR"
    assert success.provider == "deepl"
    assert success.error_message is None
    assert success.score is None

    failure = next(entry for entry in entries if entry.status == "failure")
    assert failure.category == "translation"
    assert failure.media_title == "Foo"
    assert failure.language == "es"
    assert failure.provider is None
    assert failure.error_message == "google: quota exceeded"
    assert failure.score is None


def test_list_history_includes_acquisition_success_and_failure(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie=movie)
    subtitle = _subtitle(in_memory_session, media_file, "en")
    assert subtitle.id is not None
    assert media_file.id is not None

    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle.id,
            provider="opensubtitles",
            release_name="Foo.WEB-DL",
            download_id="1",
            score=0.9,
            title_similarity=0.9,
            attempted_at=datetime.now(UTC),
        )
    )
    in_memory_session.add(
        AcquisitionFailure(
            media_file_id=media_file.id,
            language="fr",
            error_message="subdl: 500 Internal Server Error",
            failed_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    entries = list_history(in_memory_session)

    assert len(entries) == 2
    success = next(entry for entry in entries if entry.status == "success")
    assert success.category == "acquisition"
    # `AcquisitionAttempt` has no language column of its own — resolved from the target
    # `Subtitle` row it points at.
    assert success.language == "en"
    assert success.provider == "opensubtitles"
    assert success.score == 0.9
    assert success.previous_score is None

    failure = next(entry for entry in entries if entry.status == "failure")
    assert failure.category == "acquisition"
    assert failure.language == "fr"
    assert failure.error_message == "subdl: 500 Internal Server Error"
    assert failure.score is None


def test_list_history_marks_a_replacement_attempt_as_upgrade(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie=movie)
    subtitle = _subtitle(in_memory_session, media_file, "en")
    assert subtitle.id is not None

    original = AcquisitionAttempt(
        subtitle_id=subtitle.id,
        provider="opensubtitles",
        release_name="Foo.WEB-DL",
        download_id="1",
        score=0.45,
        title_similarity=0.45,
        attempted_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    in_memory_session.add(original)
    in_memory_session.commit()
    assert original.id is not None

    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle.id,
            provider="opensubtitles",
            release_name="Foo.Bluray",
            download_id="2",
            score=0.8,
            title_similarity=0.8,
            replaced_attempt_id=original.id,
            attempted_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    entries = list_history(in_memory_session)

    assert len(entries) == 2
    upgrade = next(entry for entry in entries if entry.score == 0.8)
    assert upgrade.category == "upgrade"
    assert upgrade.previous_score == 0.45

    first = next(entry for entry in entries if entry.score == 0.45)
    assert first.category == "acquisition"
    assert first.previous_score is None


def test_list_history_sorts_newest_first_and_caps_at_limit(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie=movie)
    assert media_file.id is not None
    now = datetime.now(UTC)

    for offset in range(3):
        in_memory_session.add(
            TranslationFailure(
                media_file_id=media_file.id,
                source_language="en",
                target_language="pt-BR",
                error_message=f"attempt {offset}",
                failed_at=now - timedelta(minutes=offset),
            )
        )
    in_memory_session.commit()

    entries = list_history(in_memory_session, limit=2)

    assert len(entries) == 2
    assert entries[0].error_message == "attempt 0"
    assert entries[1].error_message == "attempt 1"


def test_list_history_series_entry_title_includes_the_episode_filename(in_memory_session, tmp_path):
    series = _series(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, series=series)
    assert media_file.id is not None

    in_memory_session.add(
        TranslationFailure(
            media_file_id=media_file.id,
            source_language="en",
            target_language="pt-BR",
            error_message="deepl: timeout",
            failed_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    entries = list_history(in_memory_session)

    assert len(entries) == 1
    assert entries[0].media_title == "Bar — Foo.S01E01.mkv"
