import logging
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaKind, Movie, Series
from legendarr_backend.media_metadata.fetch_metadata import (
    fetch_metadata_for_movie,
    fetch_metadata_for_series,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry

logger = logging.getLogger(__name__)


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
