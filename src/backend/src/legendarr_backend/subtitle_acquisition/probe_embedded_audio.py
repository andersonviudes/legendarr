"""Embedded audio-track probing/extraction for the speech-to-text fallback
(ROADMAP.md 0.15.0) — same `ffprobe`/`ffmpeg` subprocess shape as
`subtitle_discovery.probe_embedded_subtitles`, but over audio streams (`-select_streams a`)
instead of subtitle ones.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddedAudioTrack:
    index: int
    codec_name: str
    language: str


def probe_embedded_audio_tracks(
    video_path: Path, *, timeout_seconds: float
) -> list[EmbeddedAudioTrack]:
    """Probe `video_path`'s container for its embedded audio streams, via `ffprobe`.

    Same missing-binary/failure posture as
    `subtitle_discovery.probe_embedded_subtitles.probe_embedded_subtitle_tracks`: a
    missing `ffprobe` logs a warning and reports no tracks rather than failing the
    caller outright; a non-zero exit against a file that *is* present raises.
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
                "a",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("embedded audio probe skipped: ffprobe not found on PATH")
        return []

    tracks = []
    for stream in json.loads(result.stdout).get("streams", []):
        tracks.append(
            EmbeddedAudioTrack(
                index=stream["index"],
                codec_name=stream.get("codec_name", ""),
                language=stream.get("tags", {}).get("language", "und"),
            )
        )
    return tracks


def extract_audio_track(
    video_path: Path,
    track: EmbeddedAudioTrack,
    output_path: Path,
    *,
    timeout_seconds: float,
) -> None:
    """Extract one embedded audio stream to `output_path` as 16kHz mono PCM `.wav` —
    the format `faster_whisper`'s own decoder (`WhisperModel.transcribe`) expects, so
    transcription never has to guess which of the container's audio streams to read.

    Same temp-file/`os.replace` and missing-`ffmpeg`-binary handling as
    `subtitle_discovery.probe_embedded_subtitles.extract_embedded_subtitle_track` — see
    that function's docstring.
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
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(temp_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("embedded audio extraction skipped: ffmpeg not found on PATH")
        return
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    os.replace(temp_path, output_path)
