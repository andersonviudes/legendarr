import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from legendarr_backend.subtitle_discovery.language_codes import normalize_language_code
from legendarr_backend.subtitle_discovery.ocr_embedded_subtitles import ocr_pgs_track
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
    IMAGE_BASED_SUBTITLE_CODECS,
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


def scan_video_subtitles(
    video_path: Path,
    *,
    extract_embedded: bool = False,
    ocr_embedded: bool = False,
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    ocr_cue_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    known_languages: frozenset[str] = frozenset(),
) -> list[DiscoveredSubtitle]:
    """Discover subtitle tracks for a video file.

    External sibling files (``*.srt``, ``*.ass``) are always considered. Embedded
    text-based tracks (SubRip, ASS/SSA, ``mov_text``) are additionally probed and
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
    """
    external = _scan_external_subtitles(video_path)
    subtitles: list[DiscoveredSubtitle] = list(external)
    if extract_embedded or ocr_embedded:
        already_covered = {normalize_language_code(language) for language in known_languages} | {
            normalize_language_code(item.language) for item in external
        }
        subtitles += _scan_embedded_subtitles(
            video_path,
            probe_timeout_seconds,
            already_covered,
            extract_embedded=extract_embedded,
            ocr_embedded=ocr_embedded,
            ocr_cue_timeout_seconds=ocr_cue_timeout_seconds,
        )
    return subtitles


def _scan_external_subtitles(video_path: Path) -> list[DiscoveredSubtitle]:
    subtitles: list[DiscoveredSubtitle] = []
    # Files this module itself extracted from an embedded track are reported by
    # `_scan_embedded_subtitles` instead — excluded here so the same file on disk
    # doesn't turn into two `Subtitle` rows with conflicting origins.
    embedded_prefix = f"{video_path.stem}.embedded."
    for sibling in video_path.parent.glob(f"{video_path.stem}*"):
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
) -> list[DiscoveredSubtitle]:
    subtitles: list[DiscoveredSubtitle] = []
    for track in probe_embedded_subtitle_tracks(video_path, timeout_seconds=probe_timeout_seconds):
        is_image_track = track.codec_name in IMAGE_BASED_SUBTITLE_CODECS
        if is_image_track and not ocr_embedded:
            continue
        if not is_image_track and not extract_embedded:
            continue
        if normalize_language_code(track.language) in already_covered_languages:
            logger.debug(
                "embedded track %d (%s) skipped for %s: %s is already covered by another subtitle",
                track.index,
                track.codec_name,
                video_path,
                track.language,
            )
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
            continue
        subtitles.append(
            DiscoveredSubtitle(
                language=normalize_language_code(track.language),
                origin=SubtitleOrigin.EMBEDDED,
                source_path=output_path,
                track_index=track.index,
                forced=track.forced,
                hearing_impaired=track.hearing_impaired,
            )
        )
    return subtitles


def _guess_language_from_filename(path: Path) -> str:
    parts = path.stem.split(".")
    return parts[-1].lower() if len(parts) > 1 else "und"
