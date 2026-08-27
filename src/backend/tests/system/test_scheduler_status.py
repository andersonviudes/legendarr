from apscheduler.schedulers.background import BackgroundScheduler
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job
from legendarr_backend.system.scheduler_status import list_scheduled_jobs


def _noop() -> None:
    pass


def _register(scheduler: BackgroundScheduler, job_id: str, **trigger_args) -> None:
    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id=job_id,
        trigger="interval",
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=False,
        **trigger_args,
    )


def test_list_scheduled_jobs_returns_a_job_registered_before_the_scheduler_starts():
    """Every periodic job is registered before `scheduler.start()`
    (`legendarr_backend/bootstrap.py`) — APScheduler only queues it tentatively then, so it
    has no `next_run_time` yet (see `scheduler_status._next_run_time`'s comment)."""
    scheduler = build_scheduler()
    _register(scheduler, "test_job", minutes=15)

    jobs = list_scheduled_jobs(scheduler)

    assert len(jobs) == 1
    assert jobs[0].job_id == "test_job"
    assert jobs[0].name == "test_job"
    assert jobs[0].queue == JobQueue.SYNC.value
    assert jobs[0].next_run_time is None
    assert "interval" in jobs[0].trigger


def test_list_scheduled_jobs_sorts_by_next_run_time_soonest_first():
    scheduler = build_scheduler()
    _register(scheduler, "later", minutes=60)
    _register(scheduler, "sooner", minutes=5)
    scheduler.start()

    try:
        jobs = list_scheduled_jobs(scheduler)
    finally:
        scheduler.shutdown(wait=False)

    assert [job.job_id for job in jobs] == ["sooner", "later"]
    assert all(job.next_run_time is not None for job in jobs)


def test_list_scheduled_jobs_returns_empty_list_for_no_jobs():
    scheduler = build_scheduler()

    assert list_scheduled_jobs(scheduler) == []
