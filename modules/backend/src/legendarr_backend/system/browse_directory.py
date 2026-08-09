from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    parent: str | None
    directories: list[str]


def list_subdirectories(path: str) -> DirectoryListing:
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
        except OSError:
            continue
    directories.sort()

    parent = str(resolved.parent) if resolved != resolved.parent else None
    return DirectoryListing(path=str(resolved), parent=parent, directories=directories)
