from pathlib import Path

from sqlmodel import Session

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.path_mapping import resolve_local_path
from legendarr_backend.media_library.models import MediaFile, Movie, Series


def resolve_media_file_owner(session: Session, media_file: MediaFile) -> Movie | Series | None:
    """The `Movie`/`Series` a `MediaFile` belongs to, or `None` if it's been deleted."""
    if media_file.movie_id is not None:
        return session.get(Movie, media_file.movie_id)
    return session.get(Series, media_file.series_id)


def resolve_media_file_path(session: Session, media_file: MediaFile) -> Path | None:
    """Resolve a `MediaFile`'s absolute local path on disk.

    Returns `None` when the owning `Movie`/`Series` or its `ArrService` connection no
    longer exists — callers treat that the same way a deleted media file would be:
    skip, don't fail. Doesn't stat the path, so an unmounted library never raises here.
    """
    item = resolve_media_file_owner(session, media_file)
    if item is None:
        return None
    arr_service = session.get(ArrService, item.arr_service_id)
    if arr_service is None:
        return None
    root = Path(resolve_local_path(arr_service, item.remote_path))
    return root / media_file.relative_path
