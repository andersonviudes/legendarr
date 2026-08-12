from pathlib import Path
from typing import cast

from sqlmodel import Session

from legendarr_backend.arr_clients.base import EpisodeItem, SeriesLibraryClient
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.path_mapping import resolve_local_path
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.media_library.models import MediaFile, Movie, Series


def resolve_media_file_owner(session: Session, media_file: MediaFile) -> Movie | Series | None:
    """The `Movie`/`Series` a `MediaFile` belongs to, or `None` if it's been deleted."""
    if media_file.movie_id is not None:
        return session.get(Movie, media_file.movie_id)
    return session.get(Series, media_file.series_id)


def resolve_media_file_episode(session: Session, media_file: MediaFile) -> EpisodeItem | None:
    """The `EpisodeItem` (season/episode number) a series `MediaFile` corresponds to,
    via a live Sonarr `list_episodes` call matched by `relative_path` — the same
    format `EpisodeItem.relative_path` and `MediaFile.relative_path` both use "so the
    two can be matched directly" (`arr_clients/base.py`).

    `None` for a movie's `MediaFile`, when the owning `Series`/`ArrService` connection
    no longer exists, when Sonarr can't be reached, or when no episode matches —
    same skip-don't-fail treatment as `resolve_media_file_path`, never raises.
    """
    if media_file.series_id is None:
        return None
    series = session.get(Series, media_file.series_id)
    if series is None:
        return None
    arr_service = session.get(ArrService, series.arr_service_id)
    if arr_service is None:
        return None
    client = build_client(arr_service)
    # `series` is only ever synced from a Sonarr connection (see
    # `sync_media_library.MEDIA_MODEL_BY_TYPE`), so `client` is always a
    # `SeriesLibraryClient` here even though `build_client`'s declared return type is
    # the broader `RadarrClient | SonarrClient` union.
    sonarr_client = cast(SeriesLibraryClient, client)
    try:
        episodes = sonarr_client.list_episodes(series.arr_id)
    except ProviderClientError:
        return None
    finally:
        client.close()
    return next(
        (episode for episode in episodes if episode.relative_path == media_file.relative_path),
        None,
    )


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
