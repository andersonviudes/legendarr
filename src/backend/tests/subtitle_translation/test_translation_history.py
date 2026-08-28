from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation.translation_history import (
    list_translation_attempts,
    record_translation_attempt,
)


def _media_file(session, tmp_path) -> MediaFile:
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
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    session.add(movie)
    session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo/Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    session.add(media_file)
    session.commit()
    return media_file


def _subtitle(session, media_file: MediaFile) -> Subtitle:
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="pt-br",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo/Foo.pt-br.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    session.add(subtitle)
    session.commit()
    return subtitle


def test_record_translation_attempt_appends_a_row(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    subtitle = _subtitle(in_memory_session, media_file)
    assert subtitle.id is not None

    record_translation_attempt(
        in_memory_session,
        subtitle.id,
        provider="deepl",
        source_language="en",
        target_language="pt-BR",
        translated_at=datetime.now(UTC),
    )
    in_memory_session.commit()

    attempts = list_translation_attempts(in_memory_session, subtitle.id)
    assert len(attempts) == 1
    assert attempts[0].provider == "deepl"
    assert attempts[0].source_language == "en"
    assert attempts[0].target_language == "pt-BR"


def test_record_translation_attempt_keeps_history_across_a_retranslation(
    in_memory_session, tmp_path
):
    media_file = _media_file(in_memory_session, tmp_path)
    subtitle = _subtitle(in_memory_session, media_file)
    assert subtitle.id is not None

    record_translation_attempt(
        in_memory_session,
        subtitle.id,
        provider="deepl",
        source_language="en",
        target_language="pt-BR",
        translated_at=datetime.now(UTC),
    )
    record_translation_attempt(
        in_memory_session,
        subtitle.id,
        provider="google",
        source_language="en",
        target_language="pt-BR",
        translated_at=datetime.now(UTC),
    )
    in_memory_session.commit()

    attempts = list_translation_attempts(in_memory_session, subtitle.id)
    assert [attempt.provider for attempt in attempts] == ["deepl", "google"]
