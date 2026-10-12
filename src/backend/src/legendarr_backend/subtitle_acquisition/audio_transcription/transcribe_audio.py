"""Speech-to-text transcription pipeline (ROADMAP.md 0.15.0) — the last-resort
acquisition source: turns an extracted embedded audio track
(`probe_embedded_audio.extract_audio_track`) into a source-language subtitle via a
local Whisper model (`faster_whisper`), then writes it out through the same
`.srt`-based discovery pipeline as an external file or an OCR'd embedded track (see
`subtitle_discovery.ocr_embedded_subtitles`).
"""

import io
import logging
import os
import threading
import wave
from collections.abc import Iterator
from pathlib import Path

from faster_whisper import WhisperModel

from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine, compose_srt

logger = logging.getLogger(__name__)

# Keyed by (model_size, download_root) — `WhisperModel` loads its weights from disk (or
# downloads them on first use) once and holds them in memory; reusing the instance
# across calls avoids paying that cost on every transcription.
_models: dict[tuple[str, str], WhisperModel] = {}
_models_lock = threading.Lock()

# `faster_whisper` decodes whatever it's handed into one float32 array and runs a single
# STFT over all of it, so its peak memory grows with the audio's length — a feature-length
# film needs gigabytes. Feeding it fixed-size slices of the extracted `.wav` instead keeps
# the peak flat however long the film is. The price: a word straddling a slice boundary can
# be clipped, so at most one per `_CHUNK_SECONDS` of audio.
_CHUNK_SECONDS = 600

# CTranslate2 already spreads a single transcription across every core, so two at once only
# double the memory without finishing sooner. Held until the transcription's thread really
# ends — including an abandoned (timed-out) one — so retries can't pile up decodes.
_transcription_slot = threading.BoundedSemaphore(1)


def _get_model(model_size: str, download_root: Path) -> WhisperModel:
    key = (model_size, str(download_root))
    with _models_lock:
        model = _models.get(key)
        if model is None:
            download_root.mkdir(parents=True, exist_ok=True)
            # int8: the checkpoints are stored as float16, which the CPU can't run natively,
            # so "default" would upcast the whole model to float32 (~4x the memory of int8).
            model = WhisperModel(
                model_size, device="cpu", compute_type="int8", download_root=str(download_root)
            )
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
    running the call on a daemon thread and giving up on it — the thread itself can't be
    force-killed, so a stuck decode keeps running in the background, but a daemon thread
    doesn't block process shutdown and isn't waited on again, so the caller genuinely
    moves on instead of blocking the job forever (a plain `ThreadPoolExecutor` doesn't
    work here: its context manager's `__exit__` calls `shutdown(wait=True)` on any exit
    path, including this one, which would block until the abandoned call finishes after
    all). A cue that transcribes to empty text is dropped, same as OCR; if nothing
    survives, `output_path` is left unwritten.
    """
    model = _get_model(model_size, model_dir)
    lines = _transcribe_with_timeout(model, audio_path, language, timeout_seconds)
    if not lines:
        return

    temp_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        temp_path.write_text(compose_srt(lines))
        os.replace(temp_path, output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _iter_wav_chunks(audio_path: Path) -> Iterator[tuple[float, io.BytesIO]]:
    """Yield `(offset_seconds, wav)` slices of `audio_path`, each a self-contained in-memory
    `.wav` of at most `_CHUNK_SECONDS` — only one slice is ever read from disk at a time."""
    with wave.open(str(audio_path), "rb") as source:
        frame_rate = source.getframerate()
        frames_per_chunk = frame_rate * _CHUNK_SECONDS
        offset_frames = 0
        while frames := source.readframes(frames_per_chunk):
            chunk = io.BytesIO()
            with wave.open(chunk, "wb") as target:
                target.setnchannels(source.getnchannels())
                target.setsampwidth(source.getsampwidth())
                target.setframerate(frame_rate)
                target.writeframes(frames)
            chunk.seek(0)
            yield offset_frames / frame_rate, chunk
            offset_frames += len(frames) // (source.getnchannels() * source.getsampwidth())


def _run_transcription(
    model: WhisperModel, audio_path: Path, language: str, abandoned: threading.Event
) -> list[SubtitleLine]:
    lines: list[SubtitleLine] = []
    for offset_seconds, chunk in _iter_wav_chunks(audio_path):
        segments, _info = model.transcribe(chunk, language=language)
        for segment in segments:
            # The caller gave up on this run (timeout) — stop at the next segment instead of
            # grinding through the rest of the film for a result nobody is waiting for.
            if abandoned.is_set():
                return lines
            text = segment.text.strip()
            if not text:
                continue
            lines.append(
                SubtitleLine(
                    index=len(lines) + 1,
                    start_ms=round((offset_seconds + segment.start) * 1000),
                    end_ms=round((offset_seconds + segment.end) * 1000),
                    text=text,
                )
            )
    return lines


def _transcribe_with_timeout(
    model: WhisperModel, audio_path: Path, language: str, timeout_seconds: float
) -> list[SubtitleLine]:
    """Run `_run_transcription` on a daemon thread and give up waiting after
    `timeout_seconds`, without joining the thread again — see `transcribe_audio_track`'s
    docstring for why a plain `Thread` is used instead of a `ThreadPoolExecutor`.

    Returns `[]` for a timeout, an exception raised by `_run_transcription` (logged from
    inside the thread, since the main thread has already given up waiting by the time a
    late exception would surface), or another transcription still holding
    `_transcription_slot` for the whole `timeout_seconds` (bounded so a wedged native call
    can't block every later transcription forever).
    """
    slot = _transcription_slot
    if not slot.acquire(timeout=timeout_seconds):
        logger.warning(
            "speech-to-text transcription of %s skipped: another transcription is still running",
            audio_path,
        )
        return []

    result: list[list[SubtitleLine]] = []
    abandoned = threading.Event()

    def _target() -> None:
        try:
            result.append(_run_transcription(model, audio_path, language, abandoned))
        except Exception:
            logger.warning("speech-to-text transcription failed for %s", audio_path, exc_info=True)
        finally:
            slot.release()

    thread = threading.Thread(target=_target, daemon=True)
    try:
        thread.start()
    except BaseException:
        slot.release()
        raise
    thread.join(timeout=timeout_seconds)
    if not result:
        abandoned.set()
        if thread.is_alive():
            logger.warning(
                "speech-to-text transcription of %s timed out after %.0fs",
                audio_path,
                timeout_seconds,
            )
        return []
    return result[0]
