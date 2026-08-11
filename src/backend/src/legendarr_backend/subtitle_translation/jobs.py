import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.subtitle_translation.translate_media_file import translate_media_file

logger = logging.getLogger(__name__)


def enqueue_full_translation_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    default_translation_provider: str | None = None,
) -> int:
    """Enqueue a translation run for every known `MediaFile` on the bulk queue.

    On-demand only — unlike `subtitle_discovery`'s scan fan-out, nothing calls this on
    an interval; per `ROADMAP.md` 0.3.0, unattended scheduling is 0.10.0. Callable from a
    future CLI command or "translate now" UI action without duplicating the fan-out logic.
    """
    media_file_ids = session.exec(select(MediaFile.id)).all()
    for media_file_id in media_file_ids:
        assert media_file_id is not None
        enqueue_translation(
            scheduler,
            media_file_id,
            JobQueue.TRANSLATE_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            default_translation_provider=default_translation_provider,
        )
    return len(media_file_ids)


def enqueue_translation(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    default_translation_provider: str | None = None,
) -> None:
    """Enqueue an ad-hoc translation of one `MediaFile` for immediate execution.

    Same `add_job` shape as `subtitle_discovery.jobs.enqueue_subtitle_scan`: a "date"
    trigger with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    re-run of the same file.
    """

    def run_translation() -> None:
        with get_session() as session:
            media_file = session.get(MediaFile, media_file_id)
            if media_file is None:
                logger.info("translation skipped: media file %d no longer exists", media_file_id)
                return
            video_path = resolve_media_file_path(session, media_file)
            if video_path is None:
                logger.info(
                    "translation skipped: owner of media file %d no longer exists",
                    media_file_id,
                )
                return
            result = translate_media_file(
                session, media_file, video_path, default_translation_provider
            )
            session.commit()
            logger.info("translation finished for media file %d: %s", media_file_id, result)

    scheduler.add_job(
        with_retry(run_translation, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=f"subtitle_translation:{media_file_id}",
        name=f"subtitle_translation:{media_file_id}",
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
