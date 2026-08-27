import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Shared with `Settings.embedded_subtitle_probe_timeout_seconds` and the
# `subtitle_discovery` call chain that threads it through — one place to change the
# fallback used wherever a caller doesn't have the real configured value on hand (tests,
# mostly; production always passes the configured timeout explicitly).
DEFAULT_PROBE_TIMEOUT_SECONDS = 30.0

# `dvd_subtitle` (VobSub) and `dvb_subtitle` (DVB) are deliberately left out — OCR support
# for them would each need their own from-scratch bitmap parser (no maintained library
# exists for either), unlike `hdmv_pgs_subtitle` below. Left as a future roadmap candidate.
TEXT_BASED_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "mov_text"}

# PGS (Blu-ray) bitmap subtitle codec — OCR'd via `ocr_embedded_subtitles.ocr_pgs_track`
# instead of `extract_embedded_subtitle_track` (ROADMAP.md 0.14.0).
IMAGE_BASED_SUBTITLE_CODECS = {"hdmv_pgs_subtitle"}


@dataclass(frozen=True)
class EmbeddedSubtitleTrack:
    index: int
    codec_name: str
    language: str
    forced: bool
    hearing_impaired: bool


def probe_embedded_subtitle_tracks(
    video_path: Path, *, timeout_seconds: float
) -> list[EmbeddedSubtitleTrack]:
    """Probe `video_path`'s container for its text-based embedded subtitle streams, via
    `ffprobe`. Reads each stream's language and forced/hearing-impaired disposition flags
    straight from the container metadata.

    A missing `ffprobe` binary is treated like `scan_subtitles_for_media_file`'s existing
    missing-video-file case: log a warning and report no embedded tracks, rather than
    failing the whole scan. A non-zero `ffprobe` exit against a file that *is* present
    (corrupt container, etc.) raises instead, for the caller's retry policy to handle.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "s",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("embedded subtitle probe skipped: ffprobe not found on PATH")
        return []

    tracks = []
    for stream in json.loads(result.stdout).get("streams", []):
        codec_name = stream.get("codec_name")
        if codec_name not in TEXT_BASED_SUBTITLE_CODECS | IMAGE_BASED_SUBTITLE_CODECS:
            continue
        disposition = stream.get("disposition", {})
        tracks.append(
            EmbeddedSubtitleTrack(
                index=stream["index"],
                codec_name=codec_name,
                language=stream.get("tags", {}).get("language", "und"),
                forced=bool(disposition.get("forced")),
                hearing_impaired=bool(disposition.get("hearing_impaired")),
            )
        )
    return tracks


def extract_embedded_subtitle_track(
    video_path: Path,
    track: EmbeddedSubtitleTrack,
    output_path: Path,
    *,
    timeout_seconds: float,
) -> None:
    """Extract one embedded subtitle stream to `output_path` as `.srt`, converting from its
    original codec (SubRip, ASS/SSA, `mov_text`) — `.srt` is the only format
    `subtitle_format`'s round-trip pipeline needs to understand.

    ffmpeg writes to a temporary sibling first and `output_path` is only replaced once it
    exits successfully — `_scan_embedded_subtitles` treats `output_path.exists()` as
    "already extracted" on a later scan, so a killed or timed-out run must not leave a
    partial `.srt` behind for that check to mistake as complete.

    `-f srt` is required, not cosmetic — the temp sibling's name ends in `.tmp`, and ffmpeg
    picks its output muxer from the filename extension alone (`-c:s` only selects the codec
    inside that container), so without it ffmpeg can't tell what to write and fails with
    "Unable to find a suitable output format" before touching the track at all.

    A missing `ffmpeg` binary is treated like `probe_embedded_subtitle_tracks`'s missing-
    `ffprobe` case: log a warning and leave `output_path` unwritten rather than raising —
    the caller skips the track when that happens instead of persisting a row for a file
    that doesn't exist.
    """
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(video_path),
                "-map",
                f"0:{track.index}",
                "-c:s",
                "srt",
                "-f",
                "srt",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("embedded subtitle extraction skipped: ffmpeg not found on PATH")
        return
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    os.replace(temp_path, output_path)


def extract_pgs_subtitle_stream(
    video_path: Path,
    track: EmbeddedSubtitleTrack,
    output_path: Path,
    *,
    timeout_seconds: float,
) -> None:
    """Dump one embedded PGS subtitle stream to `output_path` as a raw `.sup` file — a
    straight stream copy (`-c:s copy`), not a codec conversion, since ffmpeg can't convert
    a bitmap subtitle codec to text. `ocr_embedded_subtitles.ocr_pgs_track` parses the
    result and OCRs it.

    Same temp-file/`os.replace` and missing-`ffmpeg`-binary handling as
    `extract_embedded_subtitle_track` — see that function's docstring.
    """
    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(video_path),
                "-map",
                f"0:{track.index}",
                "-c:s",
                "copy",
                "-f",
                "sup",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("embedded PGS extraction skipped: ffmpeg not found on PATH")
        return
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    os.replace(temp_path, output_path)
