"""OCR pipeline for bitmap-based embedded subtitle tracks (ROADMAP.md 0.14.0) — turns a
PGS track's decoded bitmap cues (`pgs_format.parse_pgs`) into text via Tesseract, so a
Blu-ray rip's image-only subtitle track flows through the same `.srt`-based discovery
pipeline as an external file or a text-based embedded track.
"""

import logging
import os
from pathlib import Path

import pytesseract
from PIL import Image

from legendarr_backend.subtitle_discovery.pgs_format import PgsSubtitleCue, parse_pgs
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    EmbeddedSubtitleTrack,
    extract_pgs_subtitle_stream,
)
from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine, compose_srt

logger = logging.getLogger(__name__)

# ffprobe's raw ISO 639-2 language tag doesn't always match Tesseract's `.traineddata`
# naming (bundled in the Docker image, see `Dockerfile`) — only the actual mismatches need
# an entry here; anything else is passed straight through to `pytesseract`.
TESSERACT_LANG_OVERRIDES = {"chi": "chi_sim", "zho": "chi_sim"}
_FALLBACK_LANGUAGE = "eng"


def ocr_pgs_track(
    video_path: Path,
    track: EmbeddedSubtitleTrack,
    output_path: Path,
    *,
    timeout_seconds: float,
    ocr_cue_timeout_seconds: float,
) -> None:
    """OCR one embedded PGS subtitle track into `output_path` as `.srt`.

    Extracts the raw `.sup` stream to a temp sibling (`extract_pgs_subtitle_stream`),
    parses it into per-cue bitmaps (`pgs_format.parse_pgs`), OCRs each with Tesseract, and
    writes the result via `subtitle_format.compose_srt` — same temp-file/`os.replace`
    safety as `extract_embedded_subtitle_track`: a killed or failed run must not leave a
    partial `.srt` behind for a later scan's `output_path.exists()` check to mistake as
    complete. The intermediate `.sup` is always cleaned up, success or failure.

    A cue that OCRs to empty text (blank frame, unrecognizable bitmap) is dropped instead
    of being emitted as a blank line. If nothing survives OCR, `output_path` is left
    unwritten — same "nothing to report" posture as a missing `ffmpeg` binary.
    """
    sup_path = output_path.with_name(f"{output_path.name}.sup.tmp")
    try:
        extract_pgs_subtitle_stream(video_path, track, sup_path, timeout_seconds=timeout_seconds)
        if not sup_path.exists():
            # Missing ffmpeg binary — extract_pgs_subtitle_stream already logged a warning.
            return
        cues = parse_pgs(sup_path.read_bytes())
        lines = _ocr_cues(cues, track.language, ocr_cue_timeout_seconds)
        if not lines:
            return
        temp_srt_path = output_path.with_name(f"{output_path.name}.tmp")
        try:
            temp_srt_path.write_text(compose_srt(lines))
            os.replace(temp_srt_path, output_path)
        except Exception:
            temp_srt_path.unlink(missing_ok=True)
            raise
    finally:
        sup_path.unlink(missing_ok=True)


def _ocr_cues(
    cues: list[PgsSubtitleCue], language: str, timeout_seconds: float
) -> list[SubtitleLine]:
    tesseract_language = _resolve_tesseract_language(language)
    lines = []
    for index, cue in enumerate(cues, start=1):
        text = _ocr_cue_image(cue.image, tesseract_language, timeout_seconds)
        if not text:
            continue
        lines.append(SubtitleLine(index=index, start_ms=cue.start_ms, end_ms=cue.end_ms, text=text))
    return lines


def _resolve_tesseract_language(language: str) -> str:
    target = TESSERACT_LANG_OVERRIDES.get(language, language)
    try:
        available = pytesseract.get_languages(config="")
    except Exception:
        # Can't enumerate installed packs (e.g. tesseract missing) — let the per-cue OCR
        # call surface that failure instead of guessing here.
        return target
    if target in available:
        return target
    logger.warning(
        "no bundled Tesseract language pack for %r, falling back to %r",
        language,
        _FALLBACK_LANGUAGE,
    )
    return _FALLBACK_LANGUAGE


def _ocr_cue_image(image: Image.Image, language: str, timeout_seconds: float) -> str:
    try:
        # pytesseract's `timeout` is typed as `int` (whole seconds) even though the CLI
        # itself accepts fractional ones — round instead of truncating a sub-second value.
        text = pytesseract.image_to_string(
            _flatten_for_ocr(image), lang=language, timeout=round(timeout_seconds)
        )
    except Exception:
        logger.warning("OCR failed for one cue (language=%r); skipping", language, exc_info=True)
        return ""
    return text.strip()


def _flatten_for_ocr(image: Image.Image) -> Image.Image:
    """Composite the decoded RGBA bitmap onto a white background — Tesseract reads dark
    text on a light background far more reliably than text over a transparent one."""
    background = Image.new("RGB", image.size, (255, 255, 255))
    background.paste(image, mask=image.getchannel("A"))
    return background
