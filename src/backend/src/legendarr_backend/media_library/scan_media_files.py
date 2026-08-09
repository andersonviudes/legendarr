import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.path_mapping import resolve_local_path
from legendarr_backend.media_library.models import MediaFile, Movie, Series

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".m4v",
    ".avi",
    ".mov",
    ".wmv",
    ".ts",
    ".webm",
    ".mpg",
    ".mpeg",
}
_SAMPLE_MARKER = ".sample."


@dataclass(frozen=True)
class ScanResult:
    added: int
    removed: int
    size_changed: int
    skipped: bool = False


def scan_media_item(session: Session, item: Movie | Series, arr_service: ArrService) -> ScanResult:
    """Walk a media item's local directory and reconcile its `MediaFile` rows.

    A missing root directory means an unmounted drive, not deleted files — the scan
    skips the item and keeps its rows, so remounting never requires a rescan from
    scratch. I/O errors propagate so the job-level retry policy can handle them.
    """
    root = Path(resolve_local_path(arr_service, item.remote_path))
    if not root.is_dir():
        logger.warning("scan skipped for %r: %s is not a directory", item.title, root)
        return ScanResult(added=0, removed=0, size_changed=0, skipped=True)

    found = _walk_video_files(root)
    owner_column = MediaFile.movie_id if isinstance(item, Movie) else MediaFile.series_id
    existing = {
        row.relative_path: row
        for row in session.exec(select(MediaFile).where(owner_column == item.id))
    }

    now = datetime.now(UTC)
    added = 0
    size_changed = 0
    for relative_path, size in found.items():
        row = existing.pop(relative_path, None)
        if row is None:
            session.add(
                MediaFile(
                    movie_id=item.id if isinstance(item, Movie) else None,
                    series_id=item.id if isinstance(item, Series) else None,
                    relative_path=relative_path,
                    size_bytes=size,
                    scanned_at=now,
                )
            )
            added += 1
        else:
            if row.size_bytes != size:
                row.size_bytes = size
                size_changed += 1
            row.scanned_at = now
            session.add(row)

    removed = 0
    for stale in existing.values():
        session.delete(stale)
        removed += 1

    return ScanResult(added=added, removed=removed, size_changed=size_changed)


def delete_media_files(session: Session, item: Movie | Series) -> int:
    """Remove every `MediaFile` of an item — for Arr delete events, where the folder
    may already be gone and a rescan's unmounted-drive guard would keep stale rows."""
    owner_column = MediaFile.movie_id if isinstance(item, Movie) else MediaFile.series_id
    rows = session.exec(select(MediaFile).where(owner_column == item.id)).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def _walk_video_files(root: Path) -> dict[str, int]:
    """Map video files under `root` as `{posix path relative to root: size in bytes}`."""
    found: dict[str, int] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if _SAMPLE_MARKER in path.name.lower():
            continue
        found[path.relative_to(root).as_posix()] = path.stat().st_size
    return found
