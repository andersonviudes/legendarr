import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def sync_subtitle_timing(
    reference_path: Path, subtitle_path: Path, *, timeout_seconds: float
) -> bool:
    """Re-align `subtitle_path`'s cues against `reference_path` via `ffsubsync`, overwriting
    `subtitle_path` in place on success.

    `reference_path` is opaque to this function — `ffsubsync` accepts either a video (it
    decodes the audio track) or another already-correctly-timed subtitle file as its
    reference argument, and picks the right mode from the file itself. The caller
    (`subtitle_timing_sync.jobs.enqueue_timing_sync`) decides which one to pass.

    Same subprocess idiom as `probe_embedded_subtitles`: `ffsubsync` writes to a temporary
    sibling first, and `subtitle_path` is only replaced once it exits successfully, so a
    killed or timed-out run never leaves a partial `.srt` behind. The temp file keeps a
    `.srt` extension (`{stem}.tmp.srt`, not `{name}.tmp`) — `ffsubsync` picks its output
    writer from the `-o` path's extension and silently no-ops on an unrecognized one.

    `ffsubsync` can exit `0` even when it failed to write anything (e.g. that unrecognized-
    extension case), so success also requires the temp file to actually exist, not just a
    zero return code. That, a missing `ffsubsync` binary, a non-zero exit, or a timeout are
    all treated as an expected "couldn't sync this one" outcome — logged and reported as
    `False` rather than raised, same posture `translate_media_file`'s
    `TranslationResult.skipped_reason` already models.
    """
    temp_path = subtitle_path.with_name(f"{subtitle_path.stem}.tmp.srt")
    try:
        subprocess.run(
            ["ffsubsync", str(reference_path), "-i", str(subtitle_path), "-o", str(temp_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("timing sync skipped: ffsubsync not found on PATH")
        return False
    except Exception:
        logger.warning("timing sync failed for %s", subtitle_path)
        temp_path.unlink(missing_ok=True)
        return False
    if not temp_path.is_file():
        logger.warning(
            "timing sync failed for %s: ffsubsync exited 0 but wrote nothing", subtitle_path
        )
        return False
    os.replace(temp_path, subtitle_path)
    return True
