"""Orphaned-temp-file sweep (ROADMAP.md 0.22.0) — the safety net for a process killed
mid-write (OOM, `docker kill`, power loss) while extracting, OCRing, transcribing, or
timing-syncing a subtitle. Every one of those writers already cleans up after itself on
a normal exception; this only catches what a dead process can't.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile

# Every temp-sibling suffix a writer can leave behind before its `os.replace` swap-in —
# `subtitle_discovery.probe_embedded_subtitles`/`ocr_embedded_subtitles` write
# `{output}.tmp` (and `{output}.sup.tmp` for the intermediate PGS dump),
# `subtitle_acquisition.audio_transcription` writes `{output}.tmp`,
# `subtitle_timing_sync.sync_subtitle_timing` writes `{subtitle}.tmp.srt`, and
# `subtitle_acquisition.acquire_media_file_subtitle`'s speech-to-text fallback writes
# `{video}.stt.tmp.wav` (already `finally`-unlinked on every other path, so it only
# survives a hard kill).
_TEMP_FILE_SUFFIXES = (".tmp", ".tmp.srt", ".tmp.wav")


def cleanup_orphaned_temp_files(session: Session, *, min_age_minutes: float) -> int:
    """Delete abandoned temp siblings next to a tracked `MediaFile`'s video, older than
    `min_age_minutes`.

    `min_age_minutes` must stay above the slowest legitimate writer (speech-to-text
    transcription, up to `Settings.speech_to_text_timeout_seconds`) so a file a
    still-running job is actively writing is never mistaken for an orphan.

    Walks every tracked `MediaFile`'s directory once each, even when several media
    files share one (e.g. a season folder) — not the whole library tree, same
    network-mount-friendly, bounded-walk posture `resolve_media_file_path`'s other
    callers already rely on. A `MediaFile` whose owner (`Movie`/`Series`/`ArrService`)
    no longer exists, or whose directory doesn't exist (unmounted library), is skipped
    rather than failing the sweep. Returns how many files were removed.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=min_age_minutes)
    visited_dirs: set[Path] = set()
    removed = 0
    for media_file in session.exec(select(MediaFile)):
        video_path = resolve_media_file_path(session, media_file)
        if video_path is None:
            continue
        directory = video_path.parent
        if directory in visited_dirs:
            continue
        visited_dirs.add(directory)
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if not path.name.endswith(_TEMP_FILE_SUFFIXES):
                continue
            if datetime.fromtimestamp(path.stat().st_mtime, UTC) >= cutoff:
                continue
            path.unlink()
            removed += 1
    return removed
