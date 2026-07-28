import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import scan_video_subtitles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    added: int
    removed: int
    skipped: bool = False


def scan_subtitles_for_media_file(
    session: Session, media_file: MediaFile, video_path: Path
) -> ScanResult:
    """Discover external subtitles next to `video_path` and reconcile `Subtitle` rows.

    A missing video file means an unmounted drive or a stale row not yet rescanned,
    not deleted subtitles — the scan skips the file and keeps its rows, mirroring
    `scan_media_item`'s unmounted-drive guard. `relative_path` is derived from
    `media_file.relative_path`'s directory, same convention as `MediaFile` itself, so
    a subtitle row survives a path-mapping edit.
    """
    if not video_path.is_file():
        logger.warning("subtitle scan skipped: %s is not a file", video_path)
        return ScanResult(added=0, removed=0, skipped=True)

    discovered = scan_video_subtitles(video_path)
    video_dir = Path(media_file.relative_path).parent

    existing = {
        row.relative_path: row
        for row in session.exec(select(Subtitle).where(Subtitle.media_file_id == media_file.id))
    }

    now = datetime.now(UTC)
    added = 0
    for item in discovered:
        relative_path = (video_dir / item.source_path.name).as_posix()
        row = existing.pop(relative_path, None)
        if row is None:
            session.add(
                Subtitle(
                    media_file_id=media_file.id,
                    language=item.language,
                    origin=item.origin,
                    relative_path=relative_path,
                    track_index=item.track_index,
                    scanned_at=now,
                )
            )
            added += 1
        else:
            row.language = item.language
            row.origin = item.origin
            row.track_index = item.track_index
            row.scanned_at = now
            session.add(row)

    removed = 0
    for stale in existing.values():
        session.delete(stale)
        removed += 1

    return ScanResult(added=added, removed=removed)
