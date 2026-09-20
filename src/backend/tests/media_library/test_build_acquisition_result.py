from datetime import UTC, datetime

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.build_acquisition_result import build_acquisition_result
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle, AcquisitionAttempt
from legendarr_backend.subtitle_discovery.models import EmbeddedTrack, Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


def _seed_media_file(session) -> int:
    service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(service)
    session.commit()
    session.refresh(service)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/movies/Foo")
    session.add(movie)
    session.commit()
    session.refresh(movie)
    assert movie.id is not None
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    session.refresh(media_file)
    assert media_file.id is not None
    return media_file.id


def test_returns_the_success_and_message_it_was_given(in_memory_session):
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="en,fr", is_default=True
        )
    )
    in_memory_session.commit()
    media_file_id = _seed_media_file(in_memory_session)

    result = build_acquisition_result(in_memory_session, media_file_id, True, "Downloaded.")

    assert result.success is True
    assert result.message == "Downloaded."
    assert result.subtitles == []
    assert result.embedded_tracks == []
    # No subtitles yet, so both target languages of the default profile are missing.
    assert result.missing_languages == ["en", "fr"]
    assert result.has_source_subtitle is False


def test_external_subtitle_carries_provenance_and_the_latest_attempt(in_memory_session):
    """Two `AcquisitionAttempt` rows for one subtitle (an upgrade appended a newer one):
    the result must land on the highest-id attempt — the append-only overwrite the
    batched lookup relies on — not the first one fetched."""
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="en,fr", is_default=True
        )
    )
    in_memory_session.commit()
    media_file_id = _seed_media_file(in_memory_session)
    subtitle = Subtitle(
        media_file_id=media_file_id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.en.srt",
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    in_memory_session.refresh(subtitle)
    assert subtitle.id is not None
    subtitle_id = subtitle.id

    in_memory_session.add(
        AcquiredSubtitle(
            subtitle_id=subtitle_id,
            provider="opensubtitles",
            release_name="Foo.1080p",
            download_id="42",
            score=7.5,
            acquired_at=datetime.now(UTC),
        )
    )
    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle_id,
            provider="opensubtitles",
            release_name="Foo.1080p",
            download_id="42",
            score=7.5,
            title_similarity=0.9,
            resolution_matched=False,
            attempted_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle_id,
            provider="subdl",
            release_name="Foo.2160p",
            download_id="43",
            score=9.0,
            title_similarity=1.0,
            resolution_matched=True,
            source_matched=True,
            codec_matched=True,
            release_group_matched=True,
            edition_matched=True,
            attempted_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    result = build_acquisition_result(in_memory_session, media_file_id, True, "ok")

    assert len(result.subtitles) == 1
    read = result.subtitles[0]
    assert read.id == subtitle_id
    assert read.language == "en"
    assert read.origin == "external"
    assert read.provider == "opensubtitles"
    assert read.release_name == "Foo.1080p"
    assert read.score == 7.5
    assert read.resolution_matched is True
    assert read.source_matched is True
    assert read.codec_matched is True
    assert read.release_group_matched is True
    assert read.edition_matched is True
    assert result.missing_languages == ["fr"]
    assert result.has_source_subtitle is True


def test_embedded_track_joins_its_subtitle_by_track_index(in_memory_session):
    in_memory_session.add(
        LanguageProfile(
            name="Default", source_languages="en", target_languages="en,fr", is_default=True
        )
    )
    in_memory_session.commit()
    media_file_id = _seed_media_file(in_memory_session)

    subtitle = Subtitle(
        media_file_id=media_file_id,
        language="de",
        origin=SubtitleOrigin.EMBEDDED,
        relative_path="Foo.de.srt",
        content_hash="test-hash",
        track_index=2,
        size_bytes=100,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.add(
        EmbeddedTrack(
            media_file_id=media_file_id,
            track_index=2,
            codec_name="subrip",
            language="de",
            display_language="de",
            extracted=True,
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    in_memory_session.refresh(subtitle)
    assert subtitle.id is not None
    subtitle_id = subtitle.id

    result = build_acquisition_result(in_memory_session, media_file_id, True, "ok")

    assert len(result.embedded_tracks) == 1
    track = result.embedded_tracks[0]
    assert track.track_index == 2
    assert track.extracted is True
    assert track.subtitle is not None
    assert track.subtitle.id == subtitle_id
    assert track.subtitle.origin == "embedded"
    assert track.subtitle.provider is None
