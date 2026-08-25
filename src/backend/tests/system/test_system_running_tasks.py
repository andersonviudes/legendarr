from datetime import datetime, timedelta

from legendarr_backend.scheduling.running_tasks import RunningTask, get_running_tasks
from legendarr_backend.system.running_tasks import list_running_tasks


def test_list_running_tasks_returns_most_recently_started_first(
    isolated_running_tasks, monkeypatch
):
    older = RunningTask(
        job_id="older_job", name="older_job", queue="sync", started_at=datetime.now()
    )
    newer = RunningTask(
        job_id="newer_job",
        name="newer_job",
        queue="scan",
        started_at=older.started_at + timedelta(seconds=1),
    )
    monkeypatch.setattr(
        "legendarr_backend.system.running_tasks.get_running_tasks", lambda: [older, newer]
    )

    tasks = list_running_tasks()

    assert [task.job_id for task in tasks] == ["newer_job", "older_job"]


def test_list_running_tasks_reflects_the_shared_registry(isolated_running_tasks):
    assert get_running_tasks() == []
    assert list_running_tasks() == []
