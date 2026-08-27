import logging
from datetime import UTC, datetime

from apscheduler.events import EVENT_JOB_SUBMITTED, JobSubmissionEvent
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.database.engine import get_session
from legendarr_backend.logging.setup import configure_logging
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.running_tasks import attach_running_task_registry
from legendarr_backend.scheduling.scheduler import build_scheduler, register_job
from legendarr_backend.system.models import JobRun


def test_get_directories_returns_immediate_subdirectories(isolated_database, tmp_path):
    (tmp_path / "movies").mkdir()
    (tmp_path / "tv").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "not-a-dir.txt").write_text("x")

    with TestClient(create_api_app()) as client:
        response = client.get("/system/directories", params={"path": str(tmp_path)})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(tmp_path)
    assert body["parent"] == str(tmp_path.parent)
    assert body["directories"] == ["movies", "tv"]


def test_get_directories_404s_on_missing_path(isolated_database, tmp_path):
    with TestClient(create_api_app()) as client:
        response = client.get("/system/directories", params={"path": str(tmp_path / "missing")})

    assert response.status_code == 404


def test_get_directories_422s_on_file_path(isolated_database, tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")

    with TestClient(create_api_app()) as client:
        response = client.get("/system/directories", params={"path": str(file_path)})

    assert response.status_code == 422


def test_get_logs_returns_recent_lines(isolated_database, isolated_log_buffer):
    configure_logging()
    logging.getLogger("legendarr_backend.system.test_system_router").error("system test boom")

    with TestClient(create_api_app()) as client:
        response = client.get("/system/logs")

    assert response.status_code == 200
    lines = response.json()
    assert any("system test boom" in line["text"] and line["level"] == "ERROR" for line in lines)


def test_get_logs_filters_by_level(isolated_database, isolated_log_buffer):
    configure_logging()
    logging.getLogger("legendarr_backend.system.test_system_router").info(
        "info line for level filter test"
    )

    with TestClient(create_api_app()) as client:
        response = client.get("/system/logs", params={"level": "ERROR"})

    lines = response.json()
    assert not any("info line for level filter test" in line["text"] for line in lines)


def test_get_logs_422s_on_unknown_level(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/system/logs", params={"level": "NOPE"})

    assert response.status_code == 422


def _noop() -> None:
    pass


def test_get_running_tasks_returns_currently_running_tasks(
    isolated_database, isolated_running_tasks
):
    scheduler = build_scheduler()
    attach_running_task_registry(scheduler)
    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id="router_test_job",
        trigger="interval",
        minutes=1,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=False,
    )
    run_time = datetime.now(UTC)
    scheduler._dispatch_event(
        JobSubmissionEvent(EVENT_JOB_SUBMITTED, "router_test_job", "default", [run_time])
    )

    with TestClient(create_api_app()) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    tasks = response.json()
    assert any(task["job_id"] == "router_test_job" for task in tasks)


def test_get_scheduled_jobs_returns_registered_jobs(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    register_job(
        scheduler,
        _noop,
        queue=JobQueue.SYNC,
        job_id="scheduled_router_test_job",
        trigger="interval",
        minutes=15,
        retry_attempts=1,
        retry_delay_seconds=0,
        max_instances=1,
        coalesce=False,
    )

    with TestClient(app) as client:
        response = client.get("/system/jobs/scheduled")

    assert response.status_code == 200
    jobs = response.json()
    assert any(job["job_id"] == "scheduled_router_test_job" for job in jobs)


def test_get_scheduled_jobs_503s_when_scheduler_not_running(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/system/jobs/scheduled")

    assert response.status_code == 503


def test_get_job_history_returns_recorded_runs(isolated_database):
    with TestClient(create_api_app()) as client:
        with get_session() as session:
            session.add(
                JobRun(
                    job_id="history_router_test_job",
                    name="history_router_test_job",
                    queue="sync",
                    status="success",
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.get("/system/jobs/history")

    assert response.status_code == 200
    runs = response.json()
    assert any(run["job_id"] == "history_router_test_job" for run in runs)
