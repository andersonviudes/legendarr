from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.audit_trail import (
    list_acquisition_attempts,
    record_acquisition_failure,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    get_acquired_subtitle,
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.match_score import CandidateEvaluation
from legendarr_backend.subtitle_acquisition.models import AcquisitionFailure
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from sqlmodel import select


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
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo/Foo.en.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    session.add(subtitle)
    session.commit()
    return subtitle


def test_record_acquired_subtitle_records_the_attribute_match_breakdown(
    in_memory_session, tmp_path
):
    media_file = _media_file(in_memory_session, tmp_path)
    subtitle = _subtitle(in_memory_session, media_file)
    assert media_file.id is not None

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="fake",
        release_name="Foo.1080p.WEB-DL.x264-GROUP",
        download_id="1",
        evaluation=CandidateEvaluation(
            score=0.8,
            title_similarity=0.9,
            attribute_matches={"resolution": True, "source": True, "codec": False},
        ),
    )
    in_memory_session.commit()

    assert subtitle.id is not None
    attempts = list_acquisition_attempts(in_memory_session, subtitle.id)
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.score == 0.8
    assert attempt.title_similarity == 0.9
    assert attempt.resolution_matched is True
    assert attempt.source_matched is True
    assert attempt.codec_matched is False
    # Not present in `attribute_matches` — the reference had no detectable value —
    # so left `None`, not coerced to `False`.
    assert attempt.release_group_matched is None
    assert attempt.edition_matched is None
    assert attempt.replaced_attempt_id is None


def test_record_acquired_subtitle_links_an_upgrade_back_to_the_attempt_it_replaced(
    in_memory_session, tmp_path
):
    media_file = _media_file(in_memory_session, tmp_path)
    subtitle = _subtitle(in_memory_session, media_file)
    assert media_file.id is not None
    assert subtitle.id is not None

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="old-provider",
        release_name="Foo.OLD",
        download_id="old-1",
        evaluation=CandidateEvaluation(score=0.5, title_similarity=0.5, attribute_matches={}),
    )
    in_memory_session.commit()
    first_attempt = list_acquisition_attempts(in_memory_session, subtitle.id)[0]

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="new-provider",
        release_name="Foo.NEW",
        download_id="new-1",
        evaluation=CandidateEvaluation(score=0.9, title_similarity=0.9, attribute_matches={}),
    )
    in_memory_session.commit()

    attempts = list_acquisition_attempts(in_memory_session, subtitle.id)
    assert len(attempts) == 2
    second_attempt = attempts[1]
    assert second_attempt.provider == "new-provider"
    assert second_attempt.replaced_attempt_id == first_attempt.id

    # `AcquiredSubtitle` stays the current-state upsert — unaffected by the new
    # append-only attempt history living alongside it.
    metadata = get_acquired_subtitle(in_memory_session, subtitle.id)
    assert metadata is not None
    assert metadata.provider == "new-provider"


def test_record_acquisition_failure_appends_a_row(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None

    record_acquisition_failure(
        in_memory_session,
        media_file.id,
        language="en",
        error_message="opensubtitles: 401 Unauthorized",
        failed_at=datetime.now(UTC),
    )
    in_memory_session.commit()

    failures = list(in_memory_session.exec(select(AcquisitionFailure)))
    assert len(failures) == 1
    assert failures[0].media_file_id == media_file.id
    assert failures[0].language == "en"
    assert failures[0].error_message == "opensubtitles: 401 Unauthorized"
