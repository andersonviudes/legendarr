from datetime import UTC, datetime
from pathlib import Path

import pytest
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.upload_media_file_subtitle import (
    upload_subtitle_for_media_file,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
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
    movie = Movie(
        arr_service_id=service.id,
        arr_id=1,
        title="Foo",
        remote_path="/remote/Foo",
        imdb_id="tt1234567",
    )
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


@pytest.mark.parametrize("suffix", [".srt", ".ass", ".ssa", ".vtt"])
def test_upload_writes_the_file_with_the_right_name_and_rescans(
    in_memory_session, tmp_path, suffix
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)

    success, message = upload_subtitle_for_media_file(
        in_memory_session, media_file, video, "en", f"uploaded{suffix}", b"content"
    )

    assert success is True
    output = tmp_path / "Foo" / f"Foo.en{suffix}"
    assert output.read_bytes() == b"content"
    rows = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert any(row.language == "en" for row in rows)


def test_upload_rejects_a_disallowed_extension_without_writing_anything(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)

    success, message = upload_subtitle_for_media_file(
        in_memory_session, media_file, video, "en", "uploaded.txt", b"content"
    )

    assert success is False
    assert not (tmp_path / "Foo" / "Foo.en.txt").exists()
    rows = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert rows == []
