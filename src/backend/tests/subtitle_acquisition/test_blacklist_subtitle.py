from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.blacklist_subtitle import blacklist_subtitle
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import (
    is_translation_blacklisted,
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.match_score import CandidateEvaluation
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from sqlmodel import select


def _movie(session, tmp_path: Path) -> Movie:
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
    return movie


def _media_file(session, movie: Movie) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _write_video(tmp_path: Path) -> Path:
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    return video


def _subtitle(session, media_file: MediaFile, tmp_path: Path, **overrides) -> Subtitle:
    data = {
        "media_file_id": media_file.id,
        "language": "en",
        "origin": SubtitleOrigin.EXTERNAL,
        "relative_path": "Foo/Foo.en.srt",
        "content_hash": "hash",
        "scanned_at": datetime.now(UTC),
    }
    data.update(overrides)
    subtitle = Subtitle(**data)
    session.add(subtitle)
    session.commit()
    sidecar = tmp_path / "Foo" / "Foo.en.srt"
    sidecar.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n\n", encoding="utf-8")
    return subtitle


def test_blacklist_rejects_an_embedded_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    subtitle = _subtitle(in_memory_session, media_file, tmp_path, origin=SubtitleOrigin.EMBEDDED)

    success, message = blacklist_subtitle(in_memory_session, media_file, video, subtitle)

    assert success is False
    assert "external" in message.lower()


def test_blacklist_rejects_a_manually_uploaded_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    # No `AcquiredSubtitle` row, no `translated_from_hash` — same as a manual upload.
    subtitle = _subtitle(in_memory_session, media_file, tmp_path)

    success, message = blacklist_subtitle(in_memory_session, media_file, video, subtitle)

    assert success is False
    assert "can't be blacklisted" in message
    assert (tmp_path / "Foo" / "Foo.en.srt").exists()


def test_blacklist_an_acquired_subtitle_deletes_it_and_records_the_release(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    subtitle = _subtitle(in_memory_session, media_file, tmp_path)
    assert media_file.id is not None
    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="fake",
        release_name="Foo.BAD",
        download_id="bad-1",
        evaluation=CandidateEvaluation(score=0.9, title_similarity=0.9, attribute_matches={}),
    )
    in_memory_session.commit()

    success, message = blacklist_subtitle(in_memory_session, media_file, video, subtitle)

    assert success is True
    assert not (tmp_path / "Foo" / "Foo.en.srt").exists()
    rows = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert rows == []
    assert list_blacklisted_download_ids(in_memory_session, media_file.id, "en") == {
        ("fake", "bad-1")
    }


def test_blacklist_a_translated_subtitle_blocks_automatic_retranslation(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    subtitle = _subtitle(
        in_memory_session, media_file, tmp_path, translated_from_hash="source-hash"
    )
    assert media_file.id is not None

    success, message = blacklist_subtitle(in_memory_session, media_file, video, subtitle)

    assert success is True
    assert not (tmp_path / "Foo" / "Foo.en.srt").exists()
    assert is_translation_blacklisted(in_memory_session, media_file.id, "en") is True
