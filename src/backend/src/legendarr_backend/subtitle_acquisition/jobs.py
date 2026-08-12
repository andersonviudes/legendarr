import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.subtitle_acquisition.acquire_media_file_subtitle import (
    acquire_subtitle_for_media_file,
)

logger = logging.getLogger(__name__)


def enqueue_full_acquisition_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> int:
    """Enqueue an acquisition run for every known `MediaFile` on the bulk queue.

    On-demand only — same as `subtitle_translation.jobs.enqueue_full_translation_scan`
    before 0.10.0's unattended scheduling. Callable from a future CLI command or
    "acquire now" UI action without duplicating the fan-out logic.
    """
    media_file_ids = session.exec(select(MediaFile.id)).all()
    for media_file_id in media_file_ids:
        assert media_file_id is not None
        enqueue_acquisition(
            scheduler,
            media_file_id,
            JobQueue.ACQUIRE_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
    return len(media_file_ids)


def enqueue_acquisition(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Enqueue an ad-hoc acquisition of one `MediaFile` for immediate execution.

    Same `add_job` shape as `subtitle_translation.jobs.enqueue_translation`: a "date"
    trigger with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    re-run of the same file.
    """

    def run_acquisition() -> None:
        with get_session() as session:
            media_file = session.get(MediaFile, media_file_id)
            if media_file is None:
                logger.info("acquisition skipped: media file %d no longer exists", media_file_id)
                return
            video_path = resolve_media_file_path(session, media_file)
            if video_path is None:
                logger.info(
                    "acquisition skipped: owner of media file %d no longer exists",
                    media_file_id,
                )
                return
            result = acquire_subtitle_for_media_file(session, media_file, video_path)
            session.commit()
            logger.info("acquisition finished for media file %d: %s", media_file_id, result)

    scheduler.add_job(
        with_retry(run_acquisition, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=f"subtitle_acquisition:{media_file_id}",
        name=f"subtitle_acquisition:{media_file_id}",
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
