import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_translation.translate_media_file import translate_media_file

logger = logging.getLogger(__name__)


def register_translation_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic translation fan-out on the shared scheduler."""

    def fan_out() -> None:
        with get_session() as session:
            enqueued = enqueue_full_translation_scan(
                scheduler,
                session,
                retry_attempts=config.translate_retry_attempts,
                retry_delay_seconds=config.translate_retry_delay_seconds,
                default_translation_provider=config.default_translation_provider,
            )
        logger.info("translation fan-out enqueued: %d media files", enqueued)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.SYNC,
        job_id="subtitle_translation_fanout",
        trigger="interval",
        minutes=config.translate_interval_minutes,
        retry_attempts=config.translate_retry_attempts,
        retry_delay_seconds=config.translate_retry_delay_seconds,
        max_instances=config.translate_max_instances,
        coalesce=config.translate_coalesce,
    )


def enqueue_full_translation_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    default_translation_provider: str | None = None,
) -> int:
    """Enqueue a translation run for every known `MediaFile` on the bulk queue.

    Shared by the periodic fan-out job (`register_translation_job`) and the manual
    bulk/"translate now" path — same reasoning as `subtitle_discovery.jobs`'s
    `enqueue_full_subtitle_scan`.
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
    source_subtitle_id: int | None = None,
) -> None:
    """Enqueue an ad-hoc translation of one `MediaFile` for immediate execution.

    Same `add_job` shape as `subtitle_discovery.jobs.enqueue_subtitle_scan`: a "date"
    trigger with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    re-run of the same file.

    `source_subtitle_id`, when given, is passed straight through to `translate_media_file` to
    bypass its automatic source pick — the per-subtitle "Translate from this" manual-override
    trigger. Not job-id-encoded, same as every other per-file job option here: a later,
    non-overriding enqueue for the same file replaces a still-pending overriding one, and
    vice versa — last enqueue wins, same as everywhere else in this module.
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
                session,
                media_file,
                video_path,
                default_translation_provider,
                source_subtitle_id=source_subtitle_id,
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
