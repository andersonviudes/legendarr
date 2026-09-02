import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from legendarr_backend.config.config_file import AppConfigFile, load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile, MediaKind
from legendarr_backend.media_servers.notify_media_servers import (
    notify_media_servers_of_subtitle_write,
)
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.retry import with_retry
from legendarr_backend.scheduling.running_tasks import report_progress
from legendarr_backend.scheduling.scheduler import register_job
from legendarr_backend.subtitle_acquisition.acquire_media_file_subtitle import (
    acquire_subtitle_for_media_file,
)
from legendarr_backend.subtitle_acquisition.reconcile_pending_subtitles import (
    reconcile_pending_subtitles_for_series,
)
from legendarr_backend.subtitle_acquisition.upgrade_media_file_subtitle import (
    should_check_for_upgrade,
    upgrade_subtitle_for_media_file,
)
from legendarr_backend.subtitle_discovery.scan_eligibility import has_completed_subtitle_scan
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
                upgrade_recheck_after=timedelta(hours=config.acquisition_upgrade_recheck_hours),
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
    upgrade_recheck_after: timedelta,
    speech_to_text_model_size: str = "base",
    speech_to_text_timeout_seconds: float = 1800.0,
) -> int:
    """Enqueue an acquisition run for every subtitle-discovery-ready `MediaFile` on the
    bulk queue.

    Shared by the periodic fan-out job (`register_acquisition_job`) and a future
    manual/"acquire now" path — same reasoning as `subtitle_discovery.jobs`'s
    `enqueue_full_subtitle_scan`.

    Skips a file `has_completed_subtitle_scan` doesn't recognize yet — acquisition
    needs discovery's `Subtitle` rows to already reflect what's on disk, or it risks
    downloading a subtitle that's already sitting there unscanned. `upgrade_recheck_after`
    is threaded through to `run_acquisition`, not used for the enqueue filter itself: a
    file that already has a subtitle still needs to be considered here, just with its
    upgrade re-check throttled.
    """
    all_media_file_ids = session.exec(select(MediaFile.id)).all()
    media_file_ids: list[int] = []
    for media_file_id in all_media_file_ids:
        assert media_file_id is not None
        if has_completed_subtitle_scan(session, media_file_id):
            media_file_ids.append(media_file_id)
    for media_file_id in media_file_ids:
        enqueue_acquisition(
            scheduler,
            media_file_id,
            JobQueue.ACQUIRE_BULK,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            upgrade_recheck_after=upgrade_recheck_after,
            speech_to_text_model_size=speech_to_text_model_size,
            speech_to_text_timeout_seconds=speech_to_text_timeout_seconds,
        )
    return len(media_file_ids)


def enqueue_item_acquisition_scan(
    scheduler: BackgroundScheduler,
    session: Session,
    media_kind: MediaKind,
    media_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    speech_to_text_model_size: str = "base",
    speech_to_text_timeout_seconds: float = 1800.0,
    cascade: bool = False,
) -> int:
    """Enqueue an acquisition run for every `MediaFile` belonging to one movie/series.

    Shared by the "Search Subtitles" toolbar button on the movie/series detail page —
    same per-item `MediaFile` filter `media_library.jobs.enqueue_media_scan`'s cascade
    step uses, but triggered directly instead of after a disk rescan. Callers pass
    `JobQueue.ACQUIRE` for this responsive, event-triggered path, not `ACQUIRE_BULK` —
    same `SCAN` vs `SCAN_BULK` reasoning as `media_library.jobs`.
    """
    filter_column = MediaFile.movie_id if media_kind == "movie" else MediaFile.series_id
    media_file_ids = session.exec(select(MediaFile.id).where(filter_column == media_id)).all()
    for media_file_id in media_file_ids:
        assert media_file_id is not None
        enqueue_acquisition(
            scheduler,
            media_file_id,
            queue,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
            speech_to_text_model_size=speech_to_text_model_size,
            speech_to_text_timeout_seconds=speech_to_text_timeout_seconds,
            cascade=cascade,
        )
    return len(media_file_ids)


def enqueue_acquisition(
    scheduler: BackgroundScheduler,
    media_file_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
    upgrade_recheck_after: timedelta = timedelta(),
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

    Also gated on the resolved profile's `auto_translate` — a user who disabled
    automatic translation for this profile shouldn't have it silently re-enabled through
    the acquisition cascade (see `subtitle_translation.jobs.needs_translation`, the
    equivalent gate for the periodic translation fan-out).

    `upgrade_recheck_after` throttles the upgrade/replace check below (default: no
    throttle, always check) — the periodic bulk fan-out is the only caller that passes
    a real recheck window, so a manual/event-triggered acquisition still gets an
    immediate upgrade check.
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
                on_progress=lambda current, total, language, provider: report_progress(
                    job_id,
                    phase="searching",
                    current=current,
                    total=total,
                    language=language,
                    provider=provider,
                ),
            )
            session.commit()
            logger.info("acquisition finished for media file %d: %s", media_file_id, result)
            if result.acquired_language is not None:
                notify_media_servers_of_subtitle_write(session, video_path)
            # A pure no-op (neither acquired nor skipped) means a source-language
            # subtitle already existed — check whether a better release has since
            # shown up for it (ROADMAP.md 0.12.0's upgrade/replace pass), throttled by
            # `upgrade_recheck_after` so the bulk fan-out doesn't search providers again
            # for a file that was just checked.
            if (
                result.acquired_language is None
                and result.skipped_reason is None
                and should_check_for_upgrade(session, media_file, upgrade_recheck_after)
            ):
                upgrade_result = upgrade_subtitle_for_media_file(session, media_file, video_path)
                session.commit()
                logger.info("upgrade finished for media file %d: %s", media_file_id, upgrade_result)
                if upgrade_result.upgraded_language is not None:
                    notify_media_servers_of_subtitle_write(session, video_path)
            # Only cascade forward on an actual find — an unconditional cascade here would
            # oscillate forever against `subtitle_translation.jobs.run_translation`'s own
            # cascade back into acquisition on a missing source subtitle.
            if cascade and result.acquired_language is not None:
                profile = resolve_media_file_profile(session, media_file)
                if profile is not None and profile.auto_translate:
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


def enqueue_pending_subtitle_reconcile(
    scheduler: BackgroundScheduler,
    series_id: int,
    queue: JobQueue,
    *,
    retry_attempts: int,
    retry_delay_seconds: float,
) -> None:
    """Enqueue an ad-hoc `reconcile_pending_subtitles_for_series` run for immediate
    execution — the concrete `on_reconcile_pending` callback `legendarr_bootstrap`
    wires into `media_library.jobs.enqueue_media_scan`'s series cascade.

    Same one-off `"date"` trigger/`replace_existing` shape as `enqueue_acquisition` —
    a second scan of the same series racing a still-pending reconcile collapses into
    one run rather than stacking up.
    """
    job_id = f"pending_subtitle_reconcile:{series_id}"

    def run_reconcile() -> None:
        with get_session() as session:
            materialized = reconcile_pending_subtitles_for_series(session, series_id)
            session.commit()
            if materialized:
                logger.info(
                    "materialized %d pending subtitle(s) for series %d", materialized, series_id
                )

    wrapped = with_retry(
        run_reconcile, max_attempts=retry_attempts, delay_seconds=retry_delay_seconds
    )
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
