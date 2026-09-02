from datetime import datetime, timedelta

from legendarr_backend.scheduling.running_tasks import RunningTask, get_running_tasks
from legendarr_backend.system.running_tasks import list_running_tasks


def test_list_running_tasks_preserves_submission_order_within_the_same_status(
    isolated_running_tasks, monkeypatch, in_memory_session
):
    first = RunningTask(
        job_id="first_job", name="first_job", queue="sync", started_at=datetime.now()
    )
    second = RunningTask(
        job_id="second_job",
        name="second_job",
        queue="scan",
        started_at=first.started_at + timedelta(seconds=1),
    )
    monkeypatch.setattr(
        "legendarr_backend.system.running_tasks.get_running_tasks", lambda: [first, second]
    )

    tasks = list_running_tasks(in_memory_session)

    assert [task.job_id for task in tasks] == ["first_job", "second_job"]


def test_list_running_tasks_puts_running_tasks_before_queued_ones(
    isolated_running_tasks, monkeypatch, in_memory_session
):
    queued_first = RunningTask(
        job_id="scan_1", name="scan_1", queue="scan_bulk", started_at=datetime.now(), queued=True
    )
    running = RunningTask(
        job_id="scan_2",
        name="scan_2",
        queue="scan_bulk",
        started_at=queued_first.started_at + timedelta(seconds=1),
    )
    queued_second = RunningTask(
        job_id="scan_3",
        name="scan_3",
        queue="scan_bulk",
        started_at=queued_first.started_at + timedelta(seconds=2),
        queued=True,
    )
    monkeypatch.setattr(
        "legendarr_backend.system.running_tasks.get_running_tasks",
        lambda: [queued_first, running, queued_second],
    )

    tasks = list_running_tasks(in_memory_session)

    assert [task.job_id for task in tasks] == ["scan_2", "scan_1", "scan_3"]


def test_list_running_tasks_reflects_the_shared_registry(isolated_running_tasks, in_memory_session):
    assert get_running_tasks() == []
    assert list_running_tasks(in_memory_session) == []


def test_list_running_tasks_carries_the_queued_flag_through(
    isolated_running_tasks, monkeypatch, in_memory_session
):
    task = RunningTask(
        job_id="scan_2", name="scan_2", queue="scan_bulk", started_at=datetime.now(), queued=True
    )
    monkeypatch.setattr("legendarr_backend.system.running_tasks.get_running_tasks", lambda: [task])

    assert list_running_tasks(in_memory_session)[0].queued is True


def test_list_running_tasks_carries_progress_fields_through(
    isolated_running_tasks, monkeypatch, in_memory_session
):
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

    read = list_running_tasks(in_memory_session)[0]

    assert read.phase == "translating"
    assert read.current_step == 1
    assert read.total_steps == 2
    assert read.language == "pt-BR"
    assert read.provider is None
