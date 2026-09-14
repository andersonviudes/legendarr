import threading
import time
from datetime import UTC, datetime

import pytest
from legendarr_backend.database.engine import get_engine, get_session
from legendarr_backend.scheduling import job_timeout as job_timeout_module
from legendarr_backend.scheduling.job_timeout import (
    JobTimeoutError,
    abandoned_job_threads,
    configure_job_timeouts,
    job_timeout_seconds,
    with_timeout,
)
from legendarr_backend.scheduling.queues import JOB_TIMEOUT_SECONDS, JobQueue
from legendarr_backend.system.models import JobRun
from sqlmodel import SQLModel, select


def test_returns_the_wrapped_functions_result_when_it_finishes_in_time():
    wrapped = with_timeout(lambda: "done", seconds=5)

    assert wrapped() == "done"


def test_raises_job_timeout_error_when_the_run_outlives_its_budget():
    release = threading.Event()

    def slow() -> None:
        release.wait(timeout=30)

    wrapped = with_timeout(slow, seconds=0.05)
    try:
        with pytest.raises(JobTimeoutError):
            wrapped()
    finally:
        release.set()


def test_stops_waiting_instead_of_joining_the_abandoned_thread_again():
    """The whole point: the caller's thread — an APScheduler executor worker in
    production — is handed back promptly, so the queue's slot is freed even though the
    abandoned thread is still running."""
    release = threading.Event()

    def slow() -> None:
        release.wait(timeout=30)

    wrapped = with_timeout(slow, seconds=0.05)
    started = time.monotonic()
    try:
        with pytest.raises(JobTimeoutError):
            wrapped()
        assert time.monotonic() - started < 5
    finally:
        release.set()


def test_reraises_the_wrapped_functions_own_exception():
    def boom() -> None:
        raise ValueError("kaboom")

    wrapped = with_timeout(boom, seconds=5)

    with pytest.raises(ValueError, match="kaboom"):
        wrapped()


def test_a_non_positive_budget_leaves_the_function_untouched():
    def work() -> str:
        return "done"

    assert with_timeout(work, seconds=0) is work
    assert with_timeout(work, seconds=-1) is work


def test_preserves_attributes_set_on_the_wrapped_function():
    """`enqueue_*`'s sticky-cascade merge reads `scheduler.get_job(job_id).func.cascade`
    off whatever callable reached the jobstore — the wrapper must not hide it."""

    def work() -> None:
        pass

    work.cascade = True  # type: ignore[attr-defined]
    wrapped = with_timeout(work, seconds=5)

    assert getattr(wrapped, "cascade", False) is True
    assert wrapped.__name__ == "work"


def test_job_timeout_seconds_defaults_to_the_built_in_budget():
    assert job_timeout_seconds(JobQueue.SCAN) == JOB_TIMEOUT_SECONDS[JobQueue.SCAN]


def test_configure_job_timeouts_overrides_one_queue(isolated_job_timeouts):
    configure_job_timeouts({JobQueue.SCAN: 12.0})

    assert job_timeout_seconds(JobQueue.SCAN) == 12.0


def test_configure_job_timeouts_leaves_queues_it_doesnt_mention_alone(isolated_job_timeouts):
    configure_job_timeouts({JobQueue.SCAN: 12.0})

    assert job_timeout_seconds(JobQueue.TRANSLATE) == JOB_TIMEOUT_SECONDS[JobQueue.TRANSLATE]


def test_stops_abandoning_threads_once_the_ceiling_is_reached(isolated_job_timeouts, monkeypatch):
    """An abandoned thread is still inside the job body, holding its database connection
    and any provider semaphore permit. Unbounded, a dead network mount would leak one per
    budget period until the connection pool is exhausted and the whole app stops answering
    — so past the ceiling the wrapper goes back to waiting, wedging one queue instead."""
    monkeypatch.setattr(job_timeout_module, "MAX_ABANDONED_JOB_THREADS", 1)
    release = threading.Event()

    def slow() -> None:
        release.wait(timeout=30)

    try:
        with pytest.raises(JobTimeoutError):
            with_timeout(slow, seconds=0.05)()
        assert abandoned_job_threads() == 1

        outcome: list[object] = []

        def run_second() -> None:
            try:
                with_timeout(slow, seconds=0.05)()
                outcome.append("returned")
            except Exception as exc:  # pragma: no cover - only on a regression
                outcome.append(exc)

        waiter = threading.Thread(target=run_second, daemon=True)
        waiter.start()
        time.sleep(0.3)

        # Well past its budget and still neither raised nor returned: it is waiting.
        assert outcome == []

        release.set()
        waiter.join(timeout=10)
        assert outcome == ["returned"]
    finally:
        release.set()


def test_a_slow_job_that_does_come_back_frees_its_place_under_the_ceiling(isolated_job_timeouts):
    """Only genuinely-wedged threads should count against the ceiling — otherwise a run of
    merely-slow jobs would gradually disable the budget for everything else."""
    release = threading.Event()

    def slow() -> None:
        release.wait(timeout=30)

    try:
        with pytest.raises(JobTimeoutError):
            with_timeout(slow, seconds=0.05)()
        assert abandoned_job_threads() == 1

        release.set()
        time.sleep(0.1)

        assert abandoned_job_threads() == 0
    finally:
        release.set()


def test_the_wrapped_work_can_use_the_real_database_from_its_own_thread(isolated_database):
    """Every job body now runs on a thread `with_timeout` spawns rather than on the
    APScheduler executor's own worker, so the thing to prove is that opening a session
    against the real file-backed engine from there still works — SQLite rejects reusing a
    connection across threads, and `get_session()` is what keeps each thread on its own."""
    SQLModel.metadata.create_all(get_engine())

    def work() -> int:
        with get_session() as session:
            session.add(
                JobRun(
                    job_id="test_job",
                    name="test_job",
                    queue="sync",
                    status="success",
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                )
            )
            session.commit()
            return len(session.exec(select(JobRun)).all())

    assert with_timeout(work, seconds=30)() == 1
