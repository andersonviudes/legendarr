from datetime import UTC, datetime
from pathlib import Path

import pytest
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_discovery import scan_media_subtitles as scan_media_subtitles_module
from legendarr_backend.subtitle_discovery import scan_video_subtitles as scan_video_subtitles_module
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import EmbeddedSubtitleTrack
from legendarr_backend.subtitle_discovery.scan_media_subtitles import (
    scan_subtitles_for_media_file,
)
from legendarr_backend.subtitle_discovery.scan_video_subtitles import (
    DiscoveredSubtitle,
    SubtitleOrigin,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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


def _series(session, tmp_path: Path) -> Series:
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
    assert service.id is not None
    series = Series(arr_service_id=service.id, arr_id=1, title="Bar", remote_path="/remote/Bar")
    session.add(series)
    session.commit()
    return series


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


def _series_media_file(session, series: Series, relative: str) -> MediaFile:
    media_file = MediaFile(
        series_id=series.id,
        relative_path=relative,
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _subtitles(session) -> list[Subtitle]:
    return list(session.exec(select(Subtitle)).all())


def _language_profile(session, **overrides) -> LanguageProfile:
    defaults = {
        "name": "Default",
        "source_languages": "en",
        "target_languages": "pt-BR",
        "is_default": True,
    }
    defaults.update(overrides)
    profile = LanguageProfile(**defaults)
    session.add(profile)
    session.commit()
    return profile


def test_scan_persists_discovered_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    (tmp_path / "Foo" / "Foo.pt-BR.srt").touch()

    result = scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    assert result.added == 1
    assert result.removed == 0
    assert result.skipped is False
    row = _subtitles(in_memory_session)[0]
    assert row.media_file_id == media_file.id
    assert row.language == "pt-br"
    assert row.relative_path == "Foo/Foo.pt-BR.srt"


def test_rescan_removes_stale_subtitle_rows(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    sibling = tmp_path / "Foo" / "Foo.en.srt"
    sibling.touch()
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    sibling.unlink()
    result = scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    assert result.added == 0
    assert result.removed == 1
    assert _subtitles(in_memory_session) == []


def test_scan_with_missing_video_skips_and_keeps_rows(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Gone/Gone.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Gone/Gone.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    result = scan_subtitles_for_media_file(
        in_memory_session, media_file, tmp_path / "Gone" / "Gone.mkv"
    )

    assert result.skipped is True
    assert result.added == 0
    assert result.removed == 0
    assert len(_subtitles(in_memory_session)) == 1


def test_scan_persists_discovered_subtitle_for_series_media_file(in_memory_session, tmp_path):
    series = _series(in_memory_session, tmp_path)
    media_file = _series_media_file(in_memory_session, series, "Bar/Season 01/Bar.S01E01.mkv")
    video = tmp_path / "Bar" / "Season 01" / "Bar.S01E01.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    (tmp_path / "Bar" / "Season 01" / "Bar.S01E01.en.srt").touch()

    result = scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    assert result.added == 1
    row = _subtitles(in_memory_session)[0]
    assert row.media_file_id == media_file.id
    assert row.relative_path == "Bar/Season 01/Bar.S01E01.en.srt"


def test_rescan_updates_existing_subtitle_row_fields(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    sibling = tmp_path / "Foo" / "Foo.en.srt"
    sibling.touch()

    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    monkeypatch.setattr(
        scan_media_subtitles_module,
        "scan_video_subtitles",
        lambda _video_path, **_kwargs: [
            DiscoveredSubtitle(
                language="pt-br",
                origin=SubtitleOrigin.EMBEDDED,
                source_path=sibling,
                track_index=2,
            )
        ],
    )
    result = scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    assert result.added == 0
    assert result.removed == 0
    row = _subtitles(in_memory_session)[0]
    assert row.language == "pt-br"
    assert row.origin == SubtitleOrigin.EMBEDDED
    assert row.track_index == 2


def _capture_scan_video_subtitles_kwargs(monkeypatch, captured: dict) -> None:
    def _fake_scan_video_subtitles(_video_path, **kwargs):
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(
        scan_media_subtitles_module, "scan_video_subtitles", _fake_scan_video_subtitles
    )


def test_scan_skips_embedded_probing_without_an_effective_profile(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    captured: dict = {}
    _capture_scan_video_subtitles_kwargs(monkeypatch, captured)

    scan_subtitles_for_media_file(in_memory_session, media_file, video)

    assert captured["kwargs"]["extract_embedded"] is False


def test_scan_skips_embedded_probing_when_profile_disables_it(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    _language_profile(in_memory_session, extract_embedded_subtitles=False)
    captured: dict = {}
    _capture_scan_video_subtitles_kwargs(monkeypatch, captured)

    scan_subtitles_for_media_file(in_memory_session, media_file, video)

    assert captured["kwargs"]["extract_embedded"] is False


def test_scan_enables_embedded_probing_when_profile_allows_it(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    _language_profile(in_memory_session, extract_embedded_subtitles=True)
    captured: dict = {}
    _capture_scan_video_subtitles_kwargs(monkeypatch, captured)

    scan_subtitles_for_media_file(in_memory_session, media_file, video, probe_timeout_seconds=5.0)

    assert captured["kwargs"]["extract_embedded"] is True
    assert captured["kwargs"]["probe_timeout_seconds"] == 5.0


def test_scan_persists_forced_and_hearing_impaired_flags(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    embedded_srt = tmp_path / "Foo" / "Foo.embedded.2.jpn.srt"
    embedded_srt.touch()
    monkeypatch.setattr(
        scan_media_subtitles_module,
        "scan_video_subtitles",
        lambda _video_path, **_kwargs: [
            DiscoveredSubtitle(
                language="jpn",
                origin=SubtitleOrigin.EMBEDDED,
                source_path=embedded_srt,
                track_index=2,
                forced=True,
                hearing_impaired=True,
            )
        ],
    )

    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    row = _subtitles(in_memory_session)[0]
    assert row.forced is True
    assert row.hearing_impaired is True


def test_rescan_does_not_drop_an_already_extracted_embedded_subtitle_row(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    _language_profile(in_memory_session, extract_embedded_subtitles=True)
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda _video_path, _track, output_path, **_kwargs: output_path.touch(),
    )

    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()
    assert len(_subtitles(in_memory_session)) == 1

    # A previously-extracted embedded row must not count as "language already covered"
    # against itself — otherwise it gets skipped, and then deleted as stale, every scan.
    result = scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    assert result.added == 0
    assert result.removed == 0
    assert len(_subtitles(in_memory_session)) == 1


def test_scan_skips_embedded_extraction_when_an_external_subtitle_already_covers_the_language(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    (tmp_path / "Foo" / "Foo.pt-BR.srt").touch()
    _language_profile(in_memory_session, extract_embedded_subtitles=True)
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="por", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    rows = _subtitles(in_memory_session)
    assert len(rows) == 1
    assert rows[0].origin == SubtitleOrigin.EXTERNAL


def test_scan_persists_origin_as_lowercase_enum_value(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    (tmp_path / "Foo" / "Foo.en.srt").touch()

    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    stored = in_memory_session.exec(text("select origin from subtitle")).first()
    assert stored[0] == "external"


def test_unique_constraint_rejects_duplicate_relative_path(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    try:
        with pytest.raises(IntegrityError):
            in_memory_session.commit()
    finally:
        in_memory_session.rollback()


def test_deleting_media_file_cascades_to_subtitles(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie, "Foo/Foo.mkv")
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    in_memory_session.delete(media_file)
    in_memory_session.commit()

    assert _subtitles(in_memory_session) == []
