import logging
from datetime import UTC, datetime

from sqlmodel import Session

from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_metadata.client_factory import build_metadata_provider
from legendarr_backend.media_metadata.manage_metadata_provider import list_metadata_providers
from legendarr_backend.media_metadata.models import MediaMetadata, MetadataProviderConfig
from legendarr_backend.media_metadata.providers.base import MediaType, MetadataResult

logger = logging.getLogger(__name__)


def fetch_metadata_for_new_items(
    session: Session, movies: list[Movie], series: list[Series]
) -> None:
    """Fetch and persist metadata for media items a sync run just created.

    Runs every enabled+configured provider for each item and merges results with
    TheTVDB authoritative for `overview`/`poster_url`/`year`, TMDb only filling in
    whichever of those TheTVDB didn't have, and IMDb only contributing `imdb_rating` —
    the one field neither of the others has. A provider failing (or not being
    configured) never blocks the others; an item with nothing usable from any provider
    is simply left without a `MediaMetadata` row.
    """
    if not movies and not series:
        return
    providers = _enabled_providers(session)
    if not providers:
        return
    for movie in movies:
        assert movie.id is not None
        _fetch_and_store(
            session,
            providers,
            movie_id=movie.id,
            series_id=None,
            media_type="movie",
            title=movie.title,
            tvdb_id=movie.tvdb_id,
            imdb_id=movie.imdb_id,
        )
    for item in series:
        assert item.id is not None
        _fetch_and_store(
            session,
            providers,
            movie_id=None,
            series_id=item.id,
            media_type="series",
            title=item.title,
            tvdb_id=item.tvdb_id,
            imdb_id=item.imdb_id,
        )


def _enabled_providers(session: Session) -> list[MetadataProviderConfig]:
    return [
        config
        for config in list_metadata_providers(session)
        if config.enabled and config.has_credentials
    ]


def _fetch_and_store(
    session: Session,
    providers: list[MetadataProviderConfig],
    *,
    movie_id: int | None,
    series_id: int | None,
    media_type: MediaType,
    title: str,
    tvdb_id: int | None,
    imdb_id: str | None,
) -> None:
    merged: dict = {}
    for config in providers:
        result = _safe_fetch(
            config, media_type=media_type, title=title, tvdb_id=tvdb_id, imdb_id=imdb_id
        )
        if result is not None:
            _merge(merged, config.kind, result)
    if not merged:
        return
    session.add(
        MediaMetadata(
            movie_id=movie_id, series_id=series_id, fetched_at=datetime.now(UTC), **merged
        )
    )
    session.commit()


def _safe_fetch(
    config: MetadataProviderConfig,
    *,
    media_type: MediaType,
    title: str,
    tvdb_id: int | None,
    imdb_id: str | None,
) -> MetadataResult | None:
    client = build_metadata_provider(config)
    try:
        return client.fetch(media_type=media_type, title=title, tvdb_id=tvdb_id, imdb_id=imdb_id)
    except Exception:
        logger.exception("metadata fetch failed for %r via %s", title, config.kind)
        return None
    finally:
        client.close()


def _merge(merged: dict, kind: str, result: MetadataResult) -> None:
    """TheTVDB is authoritative for overview/poster/year; TMDb only fills in whichever
    of those TheTVDB left empty (so processing order between the two doesn't matter);
    IMDb only ever contributes `imdb_rating`, the one field neither of the others has."""
    if kind == "tvdb":
        if result.overview is not None:
            merged["overview"] = result.overview
        if result.poster_url is not None:
            merged["poster_url"] = result.poster_url
        if result.year is not None:
            merged["year"] = result.year
    elif kind == "tmdb":
        if result.overview is not None and "overview" not in merged:
            merged["overview"] = result.overview
        if result.poster_url is not None and "poster_url" not in merged:
            merged["poster_url"] = result.poster_url
        if result.year is not None and "year" not in merged:
            merged["year"] = result.year
    elif kind == "imdb" and result.imdb_rating is not None:
        merged["imdb_rating"] = result.imdb_rating
