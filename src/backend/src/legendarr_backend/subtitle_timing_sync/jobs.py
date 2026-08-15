import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_timing_sync.sync_subtitle_timing import sync_subtitle_timing

logger = logging.getLogger(__name__)


def enqueue_timing_sync(
    scheduler: BackgroundScheduler,
    subtitle_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    timeout_seconds: float,
) -> None:
    """Enqueue an ad-hoc timing sync of one `Subtitle` for immediate execution.

    Same `add_job` shape as `subtitle_translation.jobs.enqueue_translation`: a "date"
    trigger with `misfire_grace_time=None` and `replace_existing=True` dedupes a pending
    re-run of the same subtitle.
    """

    def run_timing_sync() -> None:
        with get_session() as session:
            subtitle = session.get(Subtitle, subtitle_id)
            if subtitle is None:
                logger.info("timing sync skipped: subtitle %d no longer exists", subtitle_id)
                return
            media_file = session.get(MediaFile, subtitle.media_file_id)
            if media_file is None:
                logger.info(
                    "timing sync skipped: subtitle %d's media file no longer exists",
                    subtitle_id,
                )
                return
            video_path = resolve_media_file_path(session, media_file)
            if video_path is None:
                logger.info(
                    "timing sync skipped: owner of subtitle %d's media file no longer exists",
                    subtitle_id,
                )
                return
            subtitle_path = video_path.parent / Path(subtitle.relative_path).name
            synced = sync_subtitle_timing(
                video_path, subtitle_path, timeout_seconds=timeout_seconds
            )
            logger.info("timing sync finished for subtitle %d: synced=%s", subtitle_id, synced)

    scheduler.add_job(
        with_retry(run_timing_sync, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds),
        "date",
        id=f"subtitle_timing_sync:{subtitle_id}",
        name=f"subtitle_timing_sync:{subtitle_id}",
        executor=queue.value,
        max_instances=1,
        replace_existing=True,
        misfire_grace_time=None,
    )
