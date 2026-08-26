import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.config.config_file import AppConfigFile, load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.media_servers.notify_media_servers import (
    notify_media_servers_of_subtitle_write,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_acquisition.acquire_media_file_subtitle import (
    acquire_subtitle_for_media_file,
)
from legendarr_backend.subtitle_acquisition.upgrade_media_file_subtitle import (
    upgrade_subtitle_for_media_file,
)
from legendarr_backend.subtitle_translation.jobs import enqueue_translation

logger = logging.getLogger(__name__)


def register_acquisition_job(
    scheduler: BackgroundScheduler,
    config: AppConfigFile,
) -> None:
    """Register the periodic acquisition fan-out on the shared scheduler."""

    def fan_out() -> None:
        with get_session() as session:
            enqueued = enqueue_full_acquisition_scan(
                scheduler,
                session,
                retry_attempts=config.acquisition_retry_attempts,
                retry_delay_seconds=config.acquisition_retry_delay_seconds,
                speech_to_text_model_size=config.speech_to_text_model_size,
                speech_to_text_timeout_seconds=config.speech_to_text_timeout_seconds,
            )
        logger.info("acquisition fan-out enqueued: %d media files", enqueued)

    register_job(
        scheduler,
        fan_out,
        queue=JobQueue.SYNC,
        job_id="subtitle_acquisition_fanout",
        trigger="interval",
        minutes=config.acquisition_interval_minutes,
        retry_attempts=config.acquisition_retry_attempts,
        retry_delay_seconds=config.acquisition_retry_delay_seconds,
        max_instances=config.acquisition_max_instances,
        coalesce=config.acquisition_coalesce,
    )


def enqueue_full_acquisition_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    speech_to_text_model_size: str = "base",
    speech_to_text_timeout_seconds: float = 1800.0,
) -> int:
    """Enqueue an acquisition run for every known `MediaFile` on the bulk queue.

    Shared by the periodic fan-out job (`register_acquisition_job`) and a future
    manual/"acquire now" path — same reasoning as `subtitle_discovery.jobs`'s
    `enqueue_full_subtitle_scan`.
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
            speech_to_text_model_size=speech_to_text_model_size,
            speech_to_text_timeout_seconds=speech_to_text_timeout_seconds,
        )
    return len(media_file_ids)


def enqueue_acquisition(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    speech_to_text_model_size: str = "base",
    speech_to_text_timeout_seconds: float = 1800.0,
    cascade: bool = False,
) -> None:
    """Enqueue an ad-hoc acquisition of one `MediaFile` for immediate execution.

    Same `add_job` shape as `subtitle_translation.jobs.enqueue_translation`: a "date"
    trigger with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    re-run of the same file.

    Same sticky-cascade merge as `subtitle_discovery.jobs.enqueue_subtitle_scan` — see
    its docstring for why: a later, non-cascading enqueue must not silently swap out a
    still-pending cascade=True job racing the same file.

    `cascade=True` chains into a translation run for the same file once this
    acquisition commits, but only when it actually found something
    (`result.acquired_language is not None`) — opt-in, same reasoning as
    `enqueue_media_scan`'s `cascade`. Not terminal: `enqueue_translation`'s own
    `run_translation` cascades back into an acquisition run (also opt-in, via a plain
    `no_source_subtitle` skip reason rather than a `cascade` flag) when translation
    itself finds no source subtitle — gating this cascade on an actual find is what
    keeps that a single extra hop instead of an infinite back-and-forth.
    """
    job_id = f"subtitle_acquisition:{media_file_id}"
    pending = scheduler.get_job(job_id)
    if pending is not None and getattr(pending.func, "cascade", False):
        cascade = True

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
            settings = get_settings()
            result = acquire_subtitle_for_media_file(
                session,
                media_file,
                video_path,
                speech_to_text_model_size=speech_to_text_model_size,
                speech_to_text_timeout_seconds=speech_to_text_timeout_seconds,
                speech_to_text_model_dir=settings.speech_to_text_model_dir,
            )
            session.commit()
            logger.info("acquisition finished for media file %d: %s", media_file_id, result)
            if result.acquired_language is not None:
                notify_media_servers_of_subtitle_write(session, video_path)
            # A pure no-op (neither acquired nor skipped) means a source-language
            # subtitle already existed — check whether a better release has since
            # shown up for it (ROADMAP.md 0.12.0's upgrade/replace pass).
            if result.acquired_language is None and result.skipped_reason is None:
                upgrade_result = upgrade_subtitle_for_media_file(session, media_file, video_path)
                session.commit()
                logger.info("upgrade finished for media file %d: %s", media_file_id, upgrade_result)
                if upgrade_result.upgraded_language is not None:
                    notify_media_servers_of_subtitle_write(session, video_path)
            # Only cascade forward on an actual find — an unconditional cascade here would
            # oscillate forever against `subtitle_translation.jobs.run_translation`'s own
            # cascade back into acquisition on a missing source subtitle.
            if cascade and result.acquired_language is not None:
                config = load_or_create_config_file(get_settings())
                enqueue_translation(
                    scheduler,
                    media_file_id,
                    JobQueue.TRANSLATE,
                    retry_attempts=config.translate_retry_attempts,
                    retry_delay_seconds=config.translate_retry_delay_seconds,
                    default_translation_provider=config.default_translation_provider,
                )

    wrapped = with_retry(
        run_acquisition, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds
    )
    setattr(wrapped, "cascade", cascade)  # noqa: B010 — direct assignment fails pyright
    scheduler.add_job(
        wrapped,
        "date",
        id=job_id,
        name=job_id,
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
