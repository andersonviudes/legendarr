import logging
from pathlib import Path

from legendarr_backend.system.schemas import DirectoryListingRead

logger = logging.getLogger(__name__)


def _single_line(value: object) -> str:
    """`str(value)` with line breaks removed — `path` is caller-supplied, and it (or the
    `OSError` message quoting it) must not be able to forge extra log lines."""
    return str(value).replace("\r\n", "").replace("\n", "").replace("\r", "")


def list_subdirectories(path: str) -> DirectoryListingRead:
    """List the immediate, non-hidden subdirectories of `path`, sorted by name.

    No recursion — the directory browser widget fetches one level deeper per click,
    like a standard file picker. Raises `FileNotFoundError` if `path` doesn't exist
    and `NotADirectoryError` if it exists but isn't a directory; the router maps both
    (and any `PermissionError`) to an HTTP status instead of letting them 500.
    """
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(path)
    if not resolved.is_dir():
        raise NotADirectoryError(path)

    directories = []
    for entry in resolved.iterdir():
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_dir():
                directories.append(entry.name)
        except OSError as exc:
            logger.warning(
                "skipped %s while listing %s: %s",
                _single_line(entry.name),
                _single_line(resolved),
                _single_line(exc),
            )
            continue
    directories.sort()

    parent = str(resolved.parent) if resolved != resolved.parent else None
    return DirectoryListingRead(path=str(resolved), parent=parent, directories=directories)
