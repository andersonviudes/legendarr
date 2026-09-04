from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_discovery.list_missing_subtitles import (
    has_source_subtitle_for_media_file,
    list_media_files_without_subtitles,
    list_missing_target_languages_by_media_file,
    missing_target_languages_for_media_file,
    target_languages_for_media_file,
    target_languages_missing_embedded_track,
)
from legendarr_backend.subtitle_discovery.models import EmbeddedTrack, Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


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
    assert with_subtitle.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=with_subtitle.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            content_hash="test-hash",
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
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-br",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.pt-br.srt",
            content_hash="test-hash",
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
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            content_hash="test-hash",
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


def test_missing_target_languages_for_media_file_matches_the_batch_version(
    in_memory_session, tmp_path
):
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
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-br",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.pt-br.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    missing = missing_target_languages_for_media_file(in_memory_session, media_file.id)

    assert missing == ["fr"]


def test_missing_target_languages_for_media_file_returns_empty_without_a_profile(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None

    missing = missing_target_languages_for_media_file(in_memory_session, media_file.id)

    assert missing == []


def test_target_languages_for_media_file_returns_every_target_language(in_memory_session, tmp_path):
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
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-br",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.pt-br.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    languages = target_languages_for_media_file(in_memory_session, media_file.id)

    # Every configured target language comes back, including "pt-BR" even though a
    # subtitle for it already exists — unlike `missing_target_languages_for_media_file`,
    # presence doesn't filter this list.
    assert languages == ["pt-BR", "fr"]


def test_target_languages_for_media_file_returns_empty_without_a_profile(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None

    languages = target_languages_for_media_file(in_memory_session, media_file.id)

    assert languages == []


def test_has_source_subtitle_true_when_a_source_language_subtitle_exists(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    in_memory_session.add(
        LanguageProfile(
            name="Default",
            source_languages="en",
            target_languages="pt-BR",
            is_default=True,
        )
    )
    in_memory_session.commit()
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    assert has_source_subtitle_for_media_file(in_memory_session, media_file.id) is True


def test_has_source_subtitle_false_without_a_source_language_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    in_memory_session.add(
        LanguageProfile(
            name="Default",
            source_languages="en",
            target_languages="pt-BR",
            is_default=True,
        )
    )
    in_memory_session.commit()
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    # Only the target language is present so far — nothing to translate from yet.
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt-br",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.pt-br.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    assert has_source_subtitle_for_media_file(in_memory_session, media_file.id) is False


def test_has_source_subtitle_false_without_a_profile(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None

    assert has_source_subtitle_for_media_file(in_memory_session, media_file.id) is False


def test_target_languages_missing_embedded_track_returns_uncovered_targets(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        EmbeddedTrack(
            media_file_id=media_file.id,
            track_index=2,
            codec_name="subrip",
            language="pt",
            display_language="pt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    # "pt-BR" is already embedded (region-blind, normalizes to "pt"); "fr" isn't.
    missing = target_languages_missing_embedded_track(
        in_memory_session, media_file.id, ["pt-BR", "fr"]
    )

    assert missing == ["fr"]


def test_target_languages_missing_embedded_track_returns_empty_when_all_covered(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        EmbeddedTrack(
            media_file_id=media_file.id,
            track_index=2,
            codec_name="subrip",
            language="pt",
            display_language="pt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    missing = target_languages_missing_embedded_track(in_memory_session, media_file.id, ["pt-BR"])

    assert missing == []


def test_target_languages_missing_embedded_track_returns_everything_without_any_embedded_track(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None

    missing = target_languages_missing_embedded_track(
        in_memory_session, media_file.id, ["pt-BR", "fr"]
    )

    assert missing == ["pt-BR", "fr"]
