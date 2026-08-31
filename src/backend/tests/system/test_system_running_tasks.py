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


def test_list_running_tasks_carries_the_queued_flag_through(isolated_running_tasks, monkeypatch):
    task = RunningTask(
        job_id="scan_2", name="scan_2", queue="scan_bulk", started_at=datetime.now(), queued=True
    )
    monkeypatch.setattr("legendarr_backend.system.running_tasks.get_running_tasks", lambda: [task])

    assert list_running_tasks()[0].queued is True


def test_list_running_tasks_carries_progress_fields_through(isolated_running_tasks, monkeypatch):
    task = RunningTask(
        job_id="translating_job",
        name="translating_job",
        queue="translate",
        started_at=datetime.now(),
        phase="translating",
        current_step=1,
        total_steps=2,
        language="pt-BR",
        provider=None,
    )
    monkeypatch.setattr("legendarr_backend.system.running_tasks.get_running_tasks", lambda: [task])

    read = list_running_tasks()[0]

    assert read.phase == "translating"
    assert read.current_step == 1
    assert read.total_steps == 2
    assert read.language == "pt-BR"
    assert read.provider is None
