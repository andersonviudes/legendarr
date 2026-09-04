import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from glob import escape as glob_escape
from pathlib import Path

from legendarr_backend.subtitle_discovery.language_codes import (
    display_language_code,
    normalize_language_code,
)
from legendarr_backend.subtitle_discovery.ocr_embedded_subtitles import ocr_pgs_track
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    IMAGE_BASED_SUBTITLE_CODECS,
    EmbeddedSubtitleTrack,
    extract_embedded_subtitle_track,
    probe_embedded_subtitle_tracks,
)

logger = logging.getLogger(__name__)


class SubtitleOrigin(StrEnum):
    EMBEDDED = "embedded"
    EXTERNAL = "external"


@dataclass(frozen=True)
class DiscoveredSubtitle:
    language: str
    origin: SubtitleOrigin
    source_path: Path
    track_index: int | None = None
    forced: bool = False
    hearing_impaired: bool = False


@dataclass(frozen=True)
class DetectedEmbeddedTrack:
    """One subtitle track `ffprobe` found in the container, whether or not it was extracted —
    the full picture `scan_media_subtitles` persists to `EmbeddedTrack`, so the UI can show a
    track that was skipped (wrong source language, a disabled extraction/OCR toggle, or
    already covered by an external subtitle) alongside the ones that were extracted.
    """

    track_index: int
    codec_name: str
    language: str
    # The tag actually shown in the UI, e.g. "pt-br" instead of `language`'s region-collapsed
    # "pt" — see `language_codes.display_language_code`. Only differs from `language` when
    # the container's own tag was already region-qualified.
    display_language: str
    forced: bool
    hearing_impaired: bool
    extracted: bool


@dataclass(frozen=True)
class SubtitleScanResult:
    subtitles: list[DiscoveredSubtitle]
    detected_embedded_tracks: list[DetectedEmbeddedTrack]


def scan_video_subtitles(
    video_path: Path,
    *,
    extract_embedded: bool = False,
    ocr_embedded: bool = False,
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    ocr_cue_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    known_languages: frozenset[str] = frozenset(),
    source_languages: frozenset[str] = frozenset(),
    force_track_index: int | None = None,
) -> SubtitleScanResult:
    """Discover subtitle tracks for a video file.

    External sibling files (``*.srt``, ``*.ass``) are always considered. Embedded
    tracks are always probed (`ffprobe` metadata only, no extraction) so `EmbeddedTrack`
    (`subtitle_discovery.models`) stays an accurate picture of the container regardless of
    any toggle. Text-based tracks (SubRip, ASS/SSA, ``mov_text``) are additionally
    extracted to ``.srt`` siblings when `extract_embedded` is set — the caller gates that
    on the file's effective `LanguageProfile.extract_embedded_subtitles`
    (see `scan_subtitles_for_media_file`). A track whose language already has an external
    subtitle — found in this same scan, or passed in via `known_languages` (the file's
    existing external `Subtitle` rows) — is skipped instead of extracted: an external
    subtitle already covers that language (possibly a manual/better translation), so
    there's nothing an extraction would add. `known_languages` deliberately excludes
    already-embedded rows: an embedded track that was previously extracted must not be
    treated as "already covered" by its own row, or it would get skipped — and then
    deleted as stale — on every following scan. A persisted embedded track's `language`
    is normalized (`language_codes.normalize_language_code`), so it's stored in the same
    ISO 639-1-ish form as external subtitles instead of ffprobe's raw ISO 639-2 tag.

    Bitmap-based embedded tracks (PGS) are OCR'd into the same kind of `.srt` sibling
    instead, gated separately on `ocr_embedded` (`LanguageProfile.ocr_embedded_subtitles`)
    — OCR is much heavier than a text-track's direct ffmpeg copy, so a profile can extract
    text tracks without paying for OCR, or vice versa.

    `source_languages` further restricts extraction/OCR to a track whose language is one of
    the file's effective `LanguageProfile.source_language_list` — empty means unrestricted,
    so a caller with no profile in hand (most existing tests) still gets the old
    extract-everything behavior. A track skipped for any reason — a disabled toggle, a
    language outside `source_languages`, already covered, or a failed extraction — is still
    reported, just as an unextracted `DetectedEmbeddedTrack`, not a `DiscoveredSubtitle`.

    `force_track_index`, when set, is the manual "extract this track anyway" override: the
    matching track bypasses every one of the above gates (toggle, `source_languages`,
    already-covered) — every other track is still filtered normally.
    """
    external = _scan_external_subtitles(video_path)
    subtitles: list[DiscoveredSubtitle] = list(external)
    detected_embedded_tracks: list[DetectedEmbeddedTrack] = []
    already_covered = {normalize_language_code(language) for language in known_languages} | {
        normalize_language_code(item.language) for item in external
    }
    embedded, detected_embedded_tracks = _scan_embedded_subtitles(
        video_path,
        probe_timeout_seconds,
        already_covered,
        extract_embedded=extract_embedded,
        ocr_embedded=ocr_embedded,
        ocr_cue_timeout_seconds=ocr_cue_timeout_seconds,
        source_languages=source_languages,
        force_track_index=force_track_index,
    )
    subtitles += embedded
    return SubtitleScanResult(
        subtitles=subtitles, detected_embedded_tracks=detected_embedded_tracks
    )


def _scan_external_subtitles(video_path: Path) -> list[DiscoveredSubtitle]:
    subtitles: list[DiscoveredSubtitle] = []
    # Files this module itself extracted from an embedded track are reported by
    # `_scan_embedded_subtitles` instead — excluded here so the same file on disk
    # doesn't turn into two `Subtitle` rows with conflicting origins.
    embedded_prefix = f"{video_path.stem}.embedded."
    # `glob_escape` is required, not cosmetic — a stem containing `[`/`]` (routine in
    # scene-release naming, e.g. "...[Bluray-1080p][EN+JA]-DHD") is otherwise parsed as
    # a glob character class and matches nothing, silently hiding real sibling subtitles.
    for sibling in video_path.parent.glob(f"{glob_escape(video_path.stem)}*"):
        if sibling.name.startswith(embedded_prefix):
            continue
        if sibling.suffix.lower() in {".srt", ".ass", ".ssa", ".vtt"}:
            subtitles.append(
                DiscoveredSubtitle(
                    language=_guess_language_from_filename(sibling),
                    origin=SubtitleOrigin.EXTERNAL,
                    source_path=sibling,
                )
            )
    return subtitles


def _scan_embedded_subtitles(
    video_path: Path,
    probe_timeout_seconds: float,
    already_covered_languages: set[str],
    *,
    extract_embedded: bool,
    ocr_embedded: bool,
    ocr_cue_timeout_seconds: float,
    source_languages: frozenset[str],
    force_track_index: int | None = None,
) -> tuple[list[DiscoveredSubtitle], list[DetectedEmbeddedTrack]]:
    subtitles: list[DiscoveredSubtitle] = []
    detected_tracks: list[DetectedEmbeddedTrack] = []
    for track in probe_embedded_subtitle_tracks(video_path, timeout_seconds=probe_timeout_seconds):
        language = normalize_language_code(track.language)
        display_language = display_language_code(track.language)
        is_image_track = track.codec_name in IMAGE_BASED_SUBTITLE_CODECS
        forced = track.index == force_track_index
        if is_image_track and not ocr_embedded and not forced:
            detected_tracks.append(_skipped_track(track, language, display_language))
            continue
        if not is_image_track and not extract_embedded and not forced:
            detected_tracks.append(_skipped_track(track, language, display_language))
            continue
        if source_languages and language not in source_languages and not forced:
            logger.debug(
                "embedded track %d (%s) skipped for %s: %s is not a configured source language",
                track.index,
                track.codec_name,
                video_path,
                track.language,
            )
            detected_tracks.append(_skipped_track(track, language, display_language))
            continue
        if language in already_covered_languages and not forced:
            logger.debug(
                "embedded track %d (%s) skipped for %s: %s is already covered by another subtitle",
                track.index,
                track.codec_name,
                video_path,
                track.language,
            )
            detected_tracks.append(_skipped_track(track, language, display_language))
            continue
        output_path = video_path.with_name(
            f"{video_path.stem}.embedded.{track.index}.{track.language}.srt"
        )
        # The track's content doesn't change without a resync, so a previously extracted
        # file is reused instead of re-running ffmpeg on every scan.
        if not output_path.exists():
            if is_image_track:
                ocr_pgs_track(
                    video_path,
                    track,
                    output_path,
                    timeout_seconds=probe_timeout_seconds,
                    ocr_cue_timeout_seconds=ocr_cue_timeout_seconds,
                )
            else:
                extract_embedded_subtitle_track(
                    video_path, track, output_path, timeout_seconds=probe_timeout_seconds
                )
        if not output_path.exists():
            # A missing `ffmpeg` binary, or an OCR pass that produced no usable text, makes
            # extraction a no-op instead of raising (see `extract_embedded_subtitle_track`/
            # `ocr_pgs_track`) — nothing was written, so there's nothing to report.
            detected_tracks.append(_skipped_track(track, language, display_language))
            continue
        subtitles.append(
            DiscoveredSubtitle(
                language=language,
                origin=SubtitleOrigin.EMBEDDED,
                source_path=output_path,
                track_index=track.index,
                forced=track.forced,
                hearing_impaired=track.hearing_impaired,
            )
        )
        detected_tracks.append(
            DetectedEmbeddedTrack(
                track_index=track.index,
                codec_name=track.codec_name,
                language=language,
                display_language=display_language,
                forced=track.forced,
                hearing_impaired=track.hearing_impaired,
                extracted=True,
            )
        )
    return subtitles, detected_tracks


def _skipped_track(
    track: EmbeddedSubtitleTrack, language: str, display_language: str
) -> DetectedEmbeddedTrack:
    return DetectedEmbeddedTrack(
        track_index=track.index,
        codec_name=track.codec_name,
        language=language,
        display_language=display_language,
        forced=track.forced,
        hearing_impaired=track.hearing_impaired,
        extracted=False,
    )


_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?$")


def _guess_language_from_filename(path: Path) -> str:
    """The convention (`<video-stem>.<language>.<ext>`, e.g. `movie.pt-BR.srt`) is what
    both this app's own downloads (`acquire_media_file_subtitle.py`) and well-behaved
    external subtitles use, but a subtitle shipped alongside the video by its release
    group often keeps the full scene release name as its filename instead, with no
    language suffix at all — the trailing dot-segment then isn't a language code but a
    release-tag fragment (e.g. `...HDR10][H265]-GROUP`). Validating the segment against
    a plausible language-code shape before trusting it keeps that fragment from being
    stored and displayed as if it were the subtitle's language.
    """
    parts = path.stem.split(".")
    if len(parts) == 1:
        return "und"
    candidate = parts[-1].lower()
    return candidate if _LANGUAGE_CODE_PATTERN.match(candidate) else "und"
