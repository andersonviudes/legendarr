from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    get_acquired_subtitle,
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


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


def test_record_acquired_subtitle_is_a_noop_when_the_subtitle_row_is_missing(
    in_memory_session, tmp_path
):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="fake",
        release_name="Foo",
        download_id="1",
        score=0.5,
    )

    # No row to find — nothing raised, nothing persisted.
    in_memory_session.commit()


def test_record_acquired_subtitle_creates_then_upserts_in_place(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo/Foo.en.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="first",
        release_name="Foo.First",
        download_id="1",
        score=0.5,
    )
    in_memory_session.commit()
    first = get_acquired_subtitle(in_memory_session, subtitle.id)
    assert first is not None
    assert first.provider == "first"
    first_id = first.id

    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="second",
        release_name="Foo.Second",
        download_id="2",
        score=0.9,
    )
    in_memory_session.commit()
    second = get_acquired_subtitle(in_memory_session, subtitle.id)

    assert second is not None
    assert second.id == first_id  # updated in place, not a second row
    assert second.provider == "second"
    assert second.release_name == "Foo.Second"
    assert second.download_id == "2"
    assert second.score == 0.9


def test_get_acquired_subtitle_returns_none_when_never_recorded(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo/Foo.en.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None

    assert get_acquired_subtitle(in_memory_session, subtitle.id) is None
