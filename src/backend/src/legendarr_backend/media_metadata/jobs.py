import logging
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaKind, Movie, Series
from legendarr_backend.media_metadata.fetch_metadata import (
    fetch_metadata_for_movie,
    fetch_metadata_for_series,
)
from legendarr_backend.media_metadata.poster_cache_cleanup import cleanup_orphaned_posters
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job

logger = logging.getLogger(__name__)


def register_metadata_refresh_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic metadata-refresh fan-out on the shared scheduler
    (ROADMAP.md 0.20.0) — wakes up `enqueue_metadata_refetch` on a schedule instead of
    only via the manual "Refetch All" button, so metadata (and cached posters, see
    `fetch_metadata._cache_poster`) for items already in the library don't go stale.
    Own retry/concurrency policy (`metadata_refresh_*`), independent of the manual
    button's `metadata_refetch_*` — a periodic job failing repeatedly shouldn't be tuned
    by the same knob as an interactive one-off click.
    """

    def fan_out() -> None:
        with get_session() as session:
            movies, series = enqueue_metadata_refetch(
                scheduler,
                session,
                retry_attempts=config.metadata_refresh_retry_attempts,
                retry_delay_seconds=config.metadata_refresh_retry_delay_seconds,
            )
        logger.info("metadata refresh fan-out enqueued: %d movies, %d series", movies, series)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.METADATA_BULK,
        job_id="media_metadata_refresh_fanout",
        trigger="interval",
        minutes=config.metadata_refresh_interval_minutes,
        retry_attempts=config.metadata_refresh_retry_attempts,
        retry_delay_seconds=config.metadata_refresh_retry_delay_seconds,
        max_instances=config.metadata_refresh_max_instances,
        coalesce=config.metadata_refresh_coalesce,
    )


def register_poster_cache_cleanup_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic poster-cache orphan sweep on the shared scheduler
    (ROADMAP.md 0.20.0). Its own schedule, independent of the metadata-refresh job
    above — orphaned files only ever appear when a movie/series leaves the library, not
    on every metadata refresh, so this doesn't need the same cadence.
    """

    def sweep() -> None:
        with get_session() as session:
            removed = cleanup_orphaned_posters(session)
        logger.info("poster cache cleanup removed %d orphaned file(s)", removed)

    register_job(
        scheduler,
        sweep,
        queue=JobQueue.METADATA_BULK,
        job_id="media_metadata_poster_cache_cleanup",
        trigger="interval",
        minutes=config.poster_cache_cleanup_interval_minutes,
        retry_attempts=config.poster_cache_cleanup_retry_attempts,
        retry_delay_seconds=config.poster_cache_cleanup_retry_delay_seconds,
        max_instances=config.poster_cache_cleanup_max_instances,
        coalesce=config.poster_cache_cleanup_coalesce,
    )


def enqueue_metadata_refetch(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> tuple[int, int]:
    """Enqueue a per-item metadata (re)fetch for every synced movie/series on the bulk
    queue.

    Manual only — the "Refetch All" button on Settings > Metadata source, for items
    that already existed before a provider was enabled/configured (`fetch_metadata_for_new_items`
    already covers brand-new items on every sync). Same shape as
    `media_library.jobs.enqueue_full_scan`. Returns `(movies_enqueued, series_enqueued)`.
    """
    enqueue = partial(
        enqueue_media_metadata_fetch,
        scheduler,
        retry_attempts=retry_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    movie_ids = session.exec(select(Movie.id)).all()
    series_ids = session.exec(select(Series.id)).all()
    for movie_id in movie_ids:
        assert movie_id is not None
        enqueue("movie", movie_id)
    for series_id in series_ids:
        assert series_id is not None
        enqueue("series", series_id)
    return len(movie_ids), len(series_ids)


def enqueue_media_metadata_fetch(
    scheduler: BackgroundScheduler,
    media_kind: MediaKind,
    media_id: int,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Enqueue an ad-hoc metadata (re)fetch for one media item for immediate execution.

    Same `add_job`-direct, stable-job-id, `replace_existing` dedupe shape as
    `media_library.jobs.enqueue_media_scan` — a second "Refetch All" click while the
    first pass is still draining collapses into the still-pending job per item instead
    of stacking up duplicate work.
    """
    job_id = f"media_metadata_fetch:{media_kind}:{media_id}"

    def run_fetch() -> None:
        with get_session() as session:
            if media_kind == "movie":
                movie = session.get(Movie, media_id)
                if movie is None:
                    logger.info("metadata refetch skipped: movie %d no longer exists", media_id)
                    return
                fetch_metadata_for_movie(session, movie)
            else:
                item = session.get(Series, media_id)
                if item is None:
                    logger.info("metadata refetch skipped: series %d no longer exists", media_id)
                    return
                fetch_metadata_for_series(session, item)

    scheduler.add_job(
        with_retry(run_fetch, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=job_id,
        name=job_id,
        executor=JobQueue.METADATA_BULK.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
