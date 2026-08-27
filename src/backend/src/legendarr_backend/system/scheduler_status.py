from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from legendarr_backend.system.schemas import ScheduledJobRead

# Sentinel used to sort a job with no `next_run_time` (paused, or added before the
# scheduler's first `start()` — see `_next_run_time` below) after every scheduled one,
# instead of letting a bare `None` blow up the comparison.
_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


def _next_run_time(job) -> datetime | None:
    # A job registered before the scheduler's first `start()` (every periodic job —
    # `legendarr_backend/bootstrap.py` registers them all ahead of `scheduler.start()`)
    # is only queued in APScheduler's `_pending_jobs`, not yet handed to the jobstore, so
    # its `next_run_time` slot is never assigned until `start()` runs — accessing it
    # straight off the `Job` object raises `AttributeError` rather than returning `None`.
    return getattr(job, "next_run_time", None)


def list_scheduled_jobs(scheduler: BackgroundScheduler) -> list[ScheduledJobRead]:
    """Return every job registered on `scheduler`, soonest-next-run first.

    One-off (`"date"`-triggered) jobs — every manual "Sync Now"/"Scan Disk"/etc. trigger —
    are gone from the jobstore by the time they run (same reasoning as
    `scheduling/running_tasks.py`'s own comment), so this naturally only ever lists the
    periodic jobs registered in `legendarr_backend/bootstrap.py`.
    """
    jobs = sorted(scheduler.get_jobs(), key=lambda job: _next_run_time(job) or _FAR_FUTURE)
    return [
        ScheduledJobRead(
            job_id=job.id,
            name=job.name,
            queue=job.executor,
            trigger=str(job.trigger),
            next_run_time=_next_run_time(job),
        )
        for job in jobs
    ]
