from pathlib import Path

from legendarr_backend.subtitle_discovery import scan_video_subtitles as scan_video_subtitles_module
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import EmbeddedSubtitleTrack
from legendarr_backend.subtitle_discovery.scan_video_subtitles import (
    DetectedEmbeddedTrack,
    SubtitleOrigin,
    scan_video_subtitles,
)


def test_scan_video_subtitles_finds_external_srt_sibling(tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    (tmp_path / "movie.pt-BR.srt").touch()

    subtitles = scan_video_subtitles(video).subtitles

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL
    assert subtitles[0].language == "pt-br"


def test_scan_video_subtitles_finds_external_sibling_with_brackets_in_the_name(tmp_path: Path):
    """A `[...]`-tagged scene-release stem (e.g. `[Bluray-1080p][EN+JA]`) must be matched
    literally — unescaped, `glob()` parses the brackets as a character class and finds
    nothing."""
    video = tmp_path / "Show - S01E01 - Title [Bluray-1080p][10bit][AAC 2.0][EN+JA]-DHD.mkv"
    video.touch()
    (tmp_path / "Show - S01E01 - Title [Bluray-1080p][10bit][AAC 2.0][EN+JA]-DHD.pt-BR.srt").touch()

    subtitles = scan_video_subtitles(video).subtitles

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL
    assert subtitles[0].language == "pt-br"


def test_scan_video_subtitles_falls_back_to_und_for_a_release_name_sibling(tmp_path: Path):
    """A subtitle shipped by the release group under the raw scene release name (no
    `.<language>.` suffix) must not have a release-tag fragment mistaken for its
    language — see `_guess_language_from_filename`."""
    video = tmp_path / "Show.S01E25.2160p.DV.HDR10.HEVC-GROUP.mkv"
    video.touch()
    (tmp_path / "Show.S01E25.2160p.DV.HDR10.HEVC-GROUP][DV HDR10][H265]-hone.srt").touch()

    subtitles = scan_video_subtitles(video).subtitles

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL
    assert subtitles[0].language == "und"


def test_scan_video_subtitles_probes_but_does_not_extract_by_default(monkeypatch, tmp_path: Path):
    """Probing (`ffprobe`) always runs so `EmbeddedTrack` reflects the container even with
    both extraction toggles off — but nothing gets extracted without one of them on."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="eng", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )

    result = scan_video_subtitles(video)

    assert result.subtitles == []
    assert result.detected_embedded_tracks == [
        DetectedEmbeddedTrack(
            track_index=2,
            codec_name="subrip",
            language="en",
            forced=False,
            hearing_impaired=False,
            extracted=False,
        )
    ]


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

    result = scan_video_subtitles(video, extract_embedded=True)

    assert len(result.subtitles) == 1
    subtitle = result.subtitles[0]
    assert subtitle.origin == SubtitleOrigin.EMBEDDED
    # Persisted normalized (ISO 639-1), unlike ffprobe's raw "jpn" tag — see language_codes.
    assert subtitle.language == "ja"
    assert subtitle.track_index == 2
    assert subtitle.hearing_impaired is True
    assert subtitle.forced is False
    assert subtitle.source_path == video.with_name("movie.embedded.2.jpn.srt")
    assert extracted == [video.with_name("movie.embedded.2.jpn.srt")]
    # The track is also reported as detected/extracted — the full picture persisted to
    # `EmbeddedTrack`, not just the `Subtitle`-bound `DiscoveredSubtitle` above.
    assert result.detected_embedded_tracks == [
        DetectedEmbeddedTrack(
            track_index=2,
            codec_name="subrip",
            language="ja",
            forced=False,
            hearing_impaired=True,
            extracted=True,
        )
    ]


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

    subtitles = scan_video_subtitles(video, extract_embedded=True).subtitles

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

    subtitles = scan_video_subtitles(video, extract_embedded=True).subtitles

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

    result = scan_video_subtitles(video, extract_embedded=True, known_languages=frozenset({"en"}))

    assert result.subtitles == []
    # Still reported as detected — just not extracted — so the UI can show it unticked.
    assert result.detected_embedded_tracks == [
        DetectedEmbeddedTrack(
            track_index=2,
            codec_name="subrip",
            language="en",
            forced=False,
            hearing_impaired=False,
            extracted=False,
        )
    ]


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
    ).subtitles

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

    result = scan_video_subtitles(video, extract_embedded=True)

    assert result.subtitles == []
    assert result.detected_embedded_tracks[0].extracted is False


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

    subtitles = scan_video_subtitles(video, extract_embedded=True).subtitles

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
    ).subtitles

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
    ).subtitles

    assert subtitles == []


def test_scan_video_subtitles_skips_embedded_track_outside_source_languages(
    monkeypatch, tmp_path: Path
):
    """A track whose language isn't one of the effective profile's Source Languages is
    detected but never extracted — the new gate, checked before the "already covered by
    an external subtitle" one."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="deu", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not extract")),
    )

    result = scan_video_subtitles(
        video, extract_embedded=True, source_languages=frozenset({"en", "ja"})
    )

    assert result.subtitles == []
    assert result.detected_embedded_tracks == [
        DetectedEmbeddedTrack(
            track_index=2,
            codec_name="subrip",
            language="de",
            forced=False,
            hearing_impaired=False,
            extracted=False,
        )
    ]


def test_scan_video_subtitles_extracts_embedded_track_within_source_languages(
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

    result = scan_video_subtitles(
        video, extract_embedded=True, source_languages=frozenset({"en", "ja"})
    )

    assert len(result.subtitles) == 1
    assert result.subtitles[0].language == "ja"
    assert result.detected_embedded_tracks[0].extracted is True


def test_scan_video_subtitles_empty_source_languages_is_unrestricted(monkeypatch, tmp_path: Path):
    """An empty `source_languages` (the default) means unrestricted — matches every
    existing caller/test above that never passes it, so a profile-less caller keeps the
    old extract-everything behavior."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="deu", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    result = scan_video_subtitles(video, extract_embedded=True, source_languages=frozenset())

    assert len(result.subtitles) == 1
    assert result.subtitles[0].language == "de"


def _pgs_track(index: int = 4, language: str = "por") -> EmbeddedSubtitleTrack:
    return EmbeddedSubtitleTrack(
        index=index,
        codec_name="hdmv_pgs_subtitle",
        language=language,
        forced=False,
        hearing_impaired=False,
    )


def test_scan_video_subtitles_ocrs_embedded_image_tracks_when_enabled(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = _pgs_track()
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("should not text-extract a PGS track")
        ),
    )
    ocrd = []

    def _fake_ocr(video_path, track, output_path, **kwargs):
        ocrd.append(output_path)
        output_path.touch()

    monkeypatch.setattr(scan_video_subtitles_module, "ocr_pgs_track", _fake_ocr)

    subtitles = scan_video_subtitles(video, ocr_embedded=True).subtitles

    assert len(subtitles) == 1
    subtitle = subtitles[0]
    assert subtitle.origin == SubtitleOrigin.EMBEDDED
    assert subtitle.language == "pt"
    assert subtitle.track_index == 4
    assert subtitle.source_path == video.with_name("movie.embedded.4.por.srt")
    assert ocrd == [video.with_name("movie.embedded.4.por.srt")]


def test_scan_video_subtitles_skips_image_tracks_when_ocr_disabled(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = _pgs_track()
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "ocr_pgs_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not OCR")),
    )

    # extract_embedded=True doesn't imply ocr_embedded — the image track is skipped, not
    # text-extracted, since ffmpeg can't convert a bitmap codec straight to `srt`.
    subtitles = scan_video_subtitles(video, extract_embedded=True, ocr_embedded=False).subtitles

    assert subtitles == []


def test_scan_video_subtitles_reuses_already_ocrd_embedded_file(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    output_path = video.with_name("movie.embedded.4.por.srt")
    output_path.touch()
    track = _pgs_track()
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "ocr_pgs_track",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not re-OCR")),
    )

    subtitles = scan_video_subtitles(video, ocr_embedded=True).subtitles

    assert len(subtitles) == 1
    assert subtitles[0].source_path == output_path


def test_scan_video_subtitles_skips_image_track_when_ocr_leaves_no_file(
    monkeypatch, tmp_path: Path
):
    """No usable OCR text (or a missing `ffmpeg` binary) leaves `output_path` unwritten —
    the track is left out of the result instead of becoming a `Subtitle` row for a file
    that was never created (same posture as the text-extraction path)."""
    video = tmp_path / "movie.mkv"
    video.touch()
    track = _pgs_track()
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(scan_video_subtitles_module, "ocr_pgs_track", lambda *a, **k: None)

    subtitles = scan_video_subtitles(video, ocr_embedded=True).subtitles

    assert subtitles == []


def test_scan_video_subtitles_force_track_index_bypasses_disabled_toggles(
    monkeypatch, tmp_path: Path
):
    """`force_track_index` — the manual "extract this track anyway" override — extracts
    a track even when both `extract_embedded` and `ocr_embedded` are off, and even
    probes for it at all (mirrors `test_scan_video_subtitles_skips_embedded_probing_by_default`,
    which asserts probing is skipped entirely with no override)."""
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

    result = scan_video_subtitles(video, force_track_index=2)

    assert len(result.subtitles) == 1
    assert result.subtitles[0].origin == SubtitleOrigin.EMBEDDED
    assert result.detected_embedded_tracks[0].extracted is True


def test_scan_video_subtitles_force_track_index_bypasses_source_languages(
    monkeypatch, tmp_path: Path
):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="deu", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    result = scan_video_subtitles(
        video,
        extract_embedded=True,
        source_languages=frozenset({"en", "ja"}),
        force_track_index=2,
    )

    assert len(result.subtitles) == 1
    assert result.subtitles[0].language == "de"


def test_scan_video_subtitles_force_track_index_bypasses_already_covered(
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
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    result = scan_video_subtitles(video, extract_embedded=True, force_track_index=2)

    embedded = [s for s in result.subtitles if s.origin == SubtitleOrigin.EMBEDDED]
    assert len(embedded) == 1


def test_scan_video_subtitles_force_track_index_only_affects_the_matching_track(
    monkeypatch, tmp_path: Path
):
    """A second, unrelated track outside `source_languages` is still gated normally in
    the same call — the override targets exactly one track index, not every track."""
    video = tmp_path / "movie.mkv"
    video.touch()
    forced_track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="deu", forced=False, hearing_impaired=False
    )
    other_track = EmbeddedSubtitleTrack(
        index=3, codec_name="subrip", language="fra", forced=False, hearing_impaired=False
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "probe_embedded_subtitle_tracks",
        lambda *a, **k: [forced_track, other_track],
    )
    monkeypatch.setattr(
        scan_video_subtitles_module,
        "extract_embedded_subtitle_track",
        lambda video_path, track, output_path, **k: output_path.touch(),
    )

    result = scan_video_subtitles(
        video,
        extract_embedded=True,
        source_languages=frozenset({"en", "ja"}),
        force_track_index=2,
    )

    assert len(result.subtitles) == 1
    assert result.subtitles[0].track_index == 2
    extracted_by_index = {t.track_index: t.extracted for t in result.detected_embedded_tracks}
    assert extracted_by_index == {2: True, 3: False}


def test_scan_video_subtitles_force_track_index_bypasses_ocr_toggle(monkeypatch, tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    track = _pgs_track()
    monkeypatch.setattr(
        scan_video_subtitles_module, "probe_embedded_subtitle_tracks", lambda *a, **k: [track]
    )

    def _fake_ocr(video_path, track, output_path, **kwargs):
        output_path.touch()

    monkeypatch.setattr(scan_video_subtitles_module, "ocr_pgs_track", _fake_ocr)

    subtitles = scan_video_subtitles(video, ocr_embedded=False, force_track_index=4).subtitles

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EMBEDDED
