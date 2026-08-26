"""Speech-to-text transcription pipeline (ROADMAP.md 0.15.0) — the last-resort
acquisition source: turns an extracted embedded audio track
(`probe_embedded_audio.extract_audio_track`) into a source-language subtitle via a
local Whisper model (`faster_whisper`), then writes it out through the same
`.srt`-based discovery pipeline as an external file or an OCR'd embedded track (see
`subtitle_discovery.ocr_embedded_subtitles`).
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path

from faster_whisper import WhisperModel

from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine, compose_srt

logger = logging.getLogger(__name__)

# Keyed by (model_size, download_root) — `WhisperModel` loads its weights from disk (or
# downloads them on first use) once and holds them in memory; reusing the instance
# across calls avoids paying that cost on every transcription.
_models: dict[tuple[str, str], WhisperModel] = {}


def _get_model(model_size: str, download_root: Path) -> WhisperModel:
    key = (model_size, str(download_root))
    model = _models.get(key)
    if model is None:
        download_root.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(model_size, device="cpu", download_root=str(download_root))
        _models[key] = model
    return model


def transcribe_audio_track(
    audio_path: Path,
    language: str,
    output_path: Path,
    *,
    model_size: str,
    model_dir: Path,
    timeout_seconds: float,
) -> None:
    """Transcribe `audio_path` (a mono 16kHz `.wav`, see `probe_embedded_audio`) into
    `output_path` as `.srt`, forcing Whisper's own recognition to `language` rather than
    letting it auto-detect — the profile's source language is already known, and
    auto-detection is one more thing that can go wrong on a short/noisy clip.

    Same temp-file/`os.replace` safety as `ocr_embedded_subtitles.ocr_pgs_track`: a
    killed or timed-out run must not leave a partial `.srt` behind. Unlike the
    subprocess-based pipelines elsewhere in this codebase (`ffmpeg`, `ffsubsync`,
    Tesseract), `faster_whisper` runs in-process, so `timeout_seconds` is enforced by
    running the call on a worker thread and giving up on it — the thread itself can't be
    force-killed, but the caller moves on instead of blocking the job forever. A
    cue that transcribes to empty text is dropped, same as OCR; if nothing survives,
    `output_path` is left unwritten.
    """
    model = _get_model(model_size, model_dir)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_transcription, model, audio_path, language)
        try:
            lines = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            logger.warning(
                "speech-to-text transcription of %s timed out after %.0fs",
                audio_path,
                timeout_seconds,
            )
            return
        except Exception:
            logger.warning("speech-to-text transcription failed for %s", audio_path, exc_info=True)
            return
    if not lines:
        return

    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        temp_path.write_text(compose_srt(lines))
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _run_transcription(model: WhisperModel, audio_path: Path, language: str) -> list[SubtitleLine]:
    segments, _info = model.transcribe(str(audio_path), language=language)
    lines = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip()
        if not text:
            continue
        lines.append(
            SubtitleLine(
                index=index,
                start_ms=round(segment.start * 1000),
                end_ms=round(segment.end * 1000),
                text=text,
            )
        )
    return lines
