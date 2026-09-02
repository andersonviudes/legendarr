import logging
from datetime import UTC, datetime

import httpx
from sqlmodel import Session, select

from legendarr_backend.config.settings import get_settings
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_metadata.client_factory import build_metadata_provider
from legendarr_backend.media_metadata.manage_metadata_provider import list_metadata_providers
from legendarr_backend.media_metadata.models import MediaMetadata, MetadataProviderConfig
from legendarr_backend.media_metadata.providers.base import MediaType, MetadataResult
from legendarr_backend.scheduling.provider_concurrency import (
    ConcurrencyCategory,
    limit_concurrency,
)

logger = logging.getLogger(__name__)

# Posters are small (a few hundred KB at most) — a short timeout is enough, and a slow
# CDN response shouldn't hold up the rest of a bulk metadata-refresh fan-out.
_POSTER_DOWNLOAD_TIMEOUT_SECONDS = 10.0


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


def fetch_metadata_for_movie(session: Session, movie: Movie) -> None:
    """(Re)fetch and persist metadata for a single movie, overwriting any existing
    `MediaMetadata` row for it. Used by the manual "Refetch All" bulk job — the
    fetch-on-sync path above uses `_fetch_and_store` directly, batching the
    `_enabled_providers` lookup across the whole sync instead of once per item."""
    assert movie.id is not None
    providers = _enabled_providers(session)
    if not providers:
        return
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


def fetch_metadata_for_series(session: Session, series: Series) -> None:
    """(Re)fetch and persist metadata for a single series — see `fetch_metadata_for_movie`."""
    assert series.id is not None
    providers = _enabled_providers(session)
    if not providers:
        return
    _fetch_and_store(
        session,
        providers,
        movie_id=None,
        series_id=series.id,
        media_type="series",
        title=series.title,
        tvdb_id=series.tvdb_id,
        imdb_id=series.imdb_id,
    )


def _enabled_providers(session: Session) -> list[MetadataProviderConfig]:
    return [
        config
        for config in list_metadata_providers(session)
        if config.enabled and config.has_credentials
    ]


def cache_poster_now(session: Session, *, media_type: MediaType, media_id: int) -> bool:
    """On-demand fallback for `legendarr_web`'s poster route: called when a page is
    about to show an item's poster and it isn't cached on disk yet — before the
    periodic refresh job has gotten to it, or after a cached file went missing. Fetches
    and writes it right now instead of waiting for the next scheduled run. Returns
    whether a poster is cached after this call — `False` if the item has no
    `MediaMetadata` row, no known `poster_url`, or the download failed.
    """
    key_column = MediaMetadata.movie_id if media_type == "movie" else MediaMetadata.series_id
    metadata = session.exec(select(MediaMetadata).where(key_column == media_id)).first()
    if metadata is None or metadata.poster_url is None:
        return False
    poster_cached_at = _cache_poster(media_type, media_id, metadata.poster_url)
    if poster_cached_at is None:
        return False
    metadata.poster_cached_at = poster_cached_at
    session.add(metadata)
    session.commit()
    return True


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
    media_id = movie_id if movie_id is not None else series_id
    assert media_id is not None
    poster_url = merged.get("poster_url")
    if poster_url is not None:
        poster_cached_at = _cache_poster(media_type, media_id, poster_url)
        if poster_cached_at is not None:
            merged["poster_cached_at"] = poster_cached_at
    existing = session.exec(
        select(MediaMetadata).where(
            MediaMetadata.movie_id == movie_id, MediaMetadata.series_id == series_id
        )
    ).first()
    if existing is None:
        session.add(
            MediaMetadata(
                movie_id=movie_id, series_id=series_id, fetched_at=datetime.now(UTC), **merged
            )
        )
    else:
        # A refetch (manual, or a second sync somehow re-offering the same "new" item)
        # overwrites the existing row in place instead of inserting a second one —
        # `movie_id`/`series_id` are unique, and the model's own docstring already
        # documents "refetching overwrites it" as the intended behavior.
        for field, value in merged.items():
            setattr(existing, field, value)
        existing.fetched_at = datetime.now(UTC)
        session.add(existing)
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
        with limit_concurrency(ConcurrencyCategory.METADATA, config.kind):
            return client.fetch(
                media_type=media_type, title=title, tvdb_id=tvdb_id, imdb_id=imdb_id
            )
    except Exception:
        logger.exception("metadata fetch failed for %r via %s", title, config.kind)
        return None
    finally:
        client.close()


def _cache_poster(media_type: MediaType, media_id: int, poster_url: str) -> datetime | None:
    """Download `poster_url` and write it to `Settings.poster_cache_dir` as
    `{media_type}_{media_id}.jpg`, so `legendarr_web`'s static mount can serve it locally
    instead of hotlinking the provider's CDN (ROADMAP.md 0.20.0).

    Always saved with a `.jpg` extension regardless of the response's actual
    `Content-Type` — TMDb/TheTVDB/OMDb all serve JPEG posters in practice, and
    `StaticFiles` picks `Content-Type` off the file extension rather than a stored value,
    so this keeps serving a plain directory instead of a second lookup. A refetch
    overwrites the same file in place, so there's no orphan from a poster changing, only
    from an item leaving the library (see `poster_cache_cleanup` in `jobs.py`).

    Never raises — a failed download just leaves the poster unavailable locally, same
    "never block the others" posture as `_safe_fetch`.
    """
    settings = get_settings()
    try:
        response = httpx.get(
            poster_url, timeout=_POSTER_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception(
            "poster download failed for %s %d from %r", media_type, media_id, poster_url
        )
        return None
    settings.poster_cache_dir.mkdir(parents=True, exist_ok=True)
    path = settings.poster_cache_dir / f"{media_type}_{media_id}.jpg"
    path.write_bytes(response.content)
    return datetime.now(UTC)


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
