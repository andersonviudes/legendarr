from pathlib import Path

from legendarr_backend.subtitle_discovery import scan_video_subtitles as scan_video_subtitles_module
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import EmbeddedSubtitleTrack
from legendarr_backend.subtitle_discovery.scan_video_subtitles import (
    SubtitleOrigin,
    scan_video_subtitles,
)


def test_scan_video_subtitles_finds_external_srt_sibling(tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    (tmp_path / "movie.pt-BR.srt").touch()

    subtitles = scan_video_subtitles(video)

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL
    assert subtitles[0].language == "pt-br"


def test_scan_video_subtitles_skips_embedded_probing_by_default(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "probe_embedded_subtitle_tracks",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not probe")),
    )

    subtitles = scan_video_subtitles(video)

    assert subtitles == []


def test_scan_video_subtitles_extracts_embedded_text_based_tracks(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=True
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    extracted = []

    def _fake_extract(video_path, track, output_path, **kwargs):
        extracted.append(output_path)
        output_path.touch()

    monkeypatch.setattr(
        scan_video_subtitles_module, "extract_embedded_subtitle_track", _fake_extract
    )

    subtitles = scan_video_subtitles(video, extract_embedded=True)

    assert len(subtitles) == 1
    subtitle = subtitles[0]
    assert subtitle.origin == SubtitleOrigin.EMBEDDED
    # Persisted normalized (ISO 639-1), unlike ffprobe's raw "jpn" tag — see language_codes.
    assert subtitle.language == "ja"
    assert subtitle.track_index == 2
    assert subtitle.hearing_impaired is True
    assert subtitle.forced is False
    assert subtitle.source_path == video.with_name("movie.embedded.2.jpn.srt")
    assert extracted == [video.with_name("movie.embedded.2.jpn.srt")]


def test_scan_video_subtitles_reuses_already_extracted_embedded_file(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    output_path = video.with_name("movie.embedded.2.jpn.srt")
    output_path.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not re-extract")),
    )

    subtitles = scan_video_subtitles(video, extract_embedded=True)

    assert len(subtitles) == 1
    assert subtitles[0].source_path == output_path


def test_scan_video_subtitles_skips_embedded_track_matching_an_external_sibling(
    monkeypatch, tmp_path: Path
):
    video = tmp_path / "movie.mkv"
    video.touch()
    (tmp_path / "movie.pt-BR.srt").touch()
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

    subtitles = scan_video_subtitles(video, extract_embedded=True)

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL


def test_scan_video_subtitles_skips_embedded_track_matching_a_known_language(
    monkeypatch, tmp_path: Path
):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="eng", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    subtitles = scan_video_subtitles(
        video, extract_embedded=True, known_languages=frozenset({"en"})
    )

    assert subtitles == []


def test_scan_video_subtitles_extracts_embedded_track_with_no_matching_known_language(
    monkeypatch, tmp_path: Path
):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    subtitles = scan_video_subtitles(
        video, extract_embedded=True, known_languages=frozenset({"en"})
    )

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EMBEDDED


def test_scan_video_subtitles_skips_track_when_extraction_leaves_no_file(
    monkeypatch, tmp_path: Path
):
    """`extract_embedded_subtitle_track` leaves `output_path` unwritten (doesn't raise)
    when `ffmpeg` is missing from PATH — the track must be left out of the result instead
    of turning into a `Subtitle` row that points at a file that was never created."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: None,  # doesn't touch output_path, same as a missing-ffmpeg no-op
    )

    subtitles = scan_video_subtitles(video, extract_embedded=True)

    assert subtitles == []


def test_scan_video_subtitles_keeps_multiple_embedded_tracks_in_the_same_language(
    monkeypatch, tmp_path: Path
):
    """Two embedded tracks in the same language (e.g. a regular track plus a commentary
    track) are both kept — "already covered" is only checked against external subtitles,
    never between embedded tracks themselves, so distinct embedded tracks aren't collapsed
    into one."""
    video = tmp_path / "movie.mkv"
    video.touch()
    main_track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="eng", forced=False, hearing_impaired=False
    )
    commentary_track = EmbeddedSubtitleTrack(
        index=3, codec_name="subrip", language="eng", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "probe_embedded_subtitle_tracks",
        lambda *a, **k: [main_track, commentary_track],
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    subtitles = scan_video_subtitles(video, extract_embedded=True)

    assert len(subtitles) == 2
    assert {s.track_index for s in subtitles} == {2, 3}


def test_scan_video_subtitles_extracts_embedded_track_with_unmapped_language_code(
    monkeypatch, tmp_path: Path
):
    """A 3-letter code this app's ISO 639-2 -> 639-1 table doesn't know (e.g. Welsh's
    "wel") falls back to being compared as-is — it must not spuriously match an unrelated
    known language just because normalization couldn't resolve it to a 2-letter code."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="wel", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    subtitles = scan_video_subtitles(
        video, extract_embedded=True, known_languages=frozenset({"en", "pt-BR"})
    )

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EMBEDDED
    assert subtitles[0].language == "wel"


def test_scan_video_subtitles_skips_embedded_track_with_unmapped_code_matching_known_language(
    monkeypatch, tmp_path: Path
):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="wel", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    subtitles = scan_video_subtitles(
        video, extract_embedded=True, known_languages=frozenset({"wel"})
    )

    assert subtitles == []
