from datetime import UTC, datetime, timedelta

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    JobEvent,
    JobExecutionEvent,
)
from legendarr_backend.database import engine as database
from legendarr_backend.database.engine import get_session
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job
from legendarr_backend.system.job_history import JobHistoryRecorder, list_job_runs
from legendarr_backend.system.models import JobRun


def _noop() -> None:
    pass


def _scheduler_with_job(job_id: str = "test_job"):
    scheduler = build_scheduler()
    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id=job_id,
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=False,
    )
    return scheduler


def _added_event(job_id: str) -> JobEvent:
    return JobEvent(EVENT_JOB_ADDED, job_id, "default")


def test_record_persists_a_successful_run(isolated_database):
    database.init_db()
    scheduler = _scheduler_with_job()
    recorder = JobHistoryRecorder()

    recorder.record(
        JobExecutionEvent(EVENT_JOB_EXECUTED, "test_job", "default", datetime.now(UTC)),
        scheduler,
        status="success",
    )

    runs = list_job_runs()
    assert len(runs) == 1
    assert runs[0].job_id == "test_job"
    assert runs[0].queue == JobQueue.SYNC.value
    assert runs[0].status == "success"
    assert runs[0].error_message is None


def test_record_persists_the_error_message_on_failure(isolated_database):
    database.init_db()
    scheduler = _scheduler_with_job()
    recorder = JobHistoryRecorder()

    recorder.record(
        JobExecutionEvent(
            EVENT_JOB_ERROR,
            "test_job",
            "default",
            datetime.now(UTC),
            exception=ValueError("boom"),
        ),
        scheduler,
        status="failure",
    )

    runs = list_job_runs()
    assert runs[0].status == "failure"
    assert "boom" in runs[0].error_message


def test_record_for_a_one_off_job_already_removed_from_the_jobstore_falls_back_to_remembered_meta(
    isolated_database,
):
    """Same regression `RunningTaskRegistry` guards against: a `"date"`-triggered one-off job
    is already gone from the jobstore by the time its completion event fires."""
    database.init_db()
    scheduler = _scheduler_with_job("one_off_job")
    recorder = JobHistoryRecorder()
    recorder.remember(_added_event("one_off_job"), scheduler)
    scheduler.remove_job("one_off_job")

    recorder.record(
        JobExecutionEvent(EVENT_JOB_EXECUTED, "one_off_job", "default", datetime.now(UTC)),
        scheduler,
        status="success",
    )

    runs = list_job_runs()
    assert runs[0].job_id == "one_off_job"
    assert runs[0].name == "one_off_job"
    assert runs[0].queue == JobQueue.SYNC.value


def test_record_for_a_never_remembered_job_falls_back_to_the_job_id(isolated_database):
    database.init_db()
    scheduler = build_scheduler()
    recorder = JobHistoryRecorder()

    recorder.record(
        JobExecutionEvent(EVENT_JOB_EXECUTED, "missing_job", "default", datetime.now(UTC)),
        scheduler,
        status="success",
    )

    runs = list_job_runs()
    assert runs[0].job_id == "missing_job"
    assert runs[0].name == "missing_job"
    assert runs[0].queue == "unknown"


def test_list_job_runs_orders_newest_first_and_respects_limit(isolated_database):
    database.init_db()
    base = datetime.now(UTC)
    with get_session() as session:
        for offset, job_id in enumerate(["a", "b", "c"]):
            session.add(
                JobRun(
                    job_id=job_id,
                    name=job_id,
                    queue="sync",
                    status="success",
                    started_at=base,
                    finished_at=base + timedelta(seconds=offset),
                )
            )
        session.commit()

    runs = list_job_runs(limit=2)

    assert [run.job_id for run in runs] == ["c", "b"]
