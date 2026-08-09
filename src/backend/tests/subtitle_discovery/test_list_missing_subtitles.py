from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_discovery.list_missing_subtitles import (
    list_media_files_without_subtitles,
    list_missing_target_languages_by_media_file,
)
from legendarr_backend.subtitle_discovery.models import Subtitle


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
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    session.add(movie)
    session.commit()
    return movie


def _media_file(session, movie: Movie, relative: str) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path=relative,
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def test_returns_only_media_files_without_any_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    with_subtitle = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    without_subtitle = _media_file(in_memory_session, movie, "Foo/Bar.mkv")
    in_memory_session.add(
        Subtitle(
            media_file_id=with_subtitle.id,
            language="en",
            origin="external",
            relative_path="Foo/Foo.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    missing = list_media_files_without_subtitles(in_memory_session)

    assert [row.id for row in missing] == [without_subtitle.id]


def test_missing_target_languages_flags_file_short_one_language(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    in_memory_session.add(
        LanguageProfile(
            name="Default",
            source_languages="en",
            target_languages="pt-BR,fr",
            is_default=True,
        )
    )
    in_memory_session.commit()
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-br",
            origin="external",
            relative_path="Foo/Foo.pt-br.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    missing = list_missing_target_languages_by_media_file(in_memory_session)

    assert missing == {media_file.id: ["fr"]}


def test_missing_target_languages_omits_file_with_every_target_language(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="en", is_default=True
        )
    )
    in_memory_session.commit()
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin="external",
            relative_path="Foo/Foo.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    missing = list_missing_target_languages_by_media_file(in_memory_session)

    assert missing == {}


def test_missing_target_languages_excludes_file_with_no_effective_profile(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    _media_file(in_memory_session, movie, "Foo/Foo.mkv")

    missing = list_missing_target_languages_by_media_file(in_memory_session)

    assert missing == {}
