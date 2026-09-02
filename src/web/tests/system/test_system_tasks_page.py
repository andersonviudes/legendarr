import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_TASK = {
    "job_id": "media_library_scan_fanout",
    "name": "media_library_scan_fanout",
    "queue": "sync",
    "started_at": "2026-08-24T10:15:30.123456",
}

_QUEUED_TASK = {
    "job_id": "subtitle_scan:2",
    "name": "subtitle_scan:2",
    "queue": "scan_bulk",
    "started_at": "2026-08-24T10:15:30.123456",
    "queued": True,
}

_TASK_WITH_PROGRESS = {
    "job_id": "subtitle_translation:1",
    "name": "subtitle_translation:1",
    "queue": "translate",
    "started_at": "2026-08-24T10:15:30.123456",
    "phase": "translating",
    "current_step": 1,
    "total_steps": 2,
    "language": "pt-BR",
    "provider": None,
}

_SCHEDULED_JOB = {
    "job_id": "media_library_sync",
    "name": "media_library_sync",
    "queue": "sync",
    "trigger": "interval[0:15:00]",
    "next_run_time": "2026-08-27T22:15:00+00:00",
}

_JOB_RUN = {
    "job_id": "media_library_sync",
    "name": "media_library_sync",
    "queue": "sync",
    "status": "failure",
    "started_at": "2026-08-27T22:00:00+00:00",
    "finished_at": "2026-08-27T22:00:05+00:00",
    "error_message": "connection refused",
}


def _tasks_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/tasks/running":
        return httpx.Response(200, json=[_TASK])
    return httpx.Response(200, json=[])


def _tasks_with_progress_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/tasks/running":
        return httpx.Response(200, json=[_TASK_WITH_PROGRESS])
    return httpx.Response(200, json=[])


def _queued_task_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/tasks/running":
        return httpx.Response(200, json=[_QUEUED_TASK])
    return httpx.Response(200, json=[])


def _no_tasks_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _scheduling_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/jobs/scheduled":
        return httpx.Response(200, json=[_SCHEDULED_JOB])
    if request.url.path == "/system/jobs/history":
        return httpx.Response(200, json=[_JOB_RUN])
    return httpx.Response(200, json=[])


def test_tasks_page_lists_running_tasks(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/")

    assert response.status_code == 200
    assert "media_library_scan_fanout" in response.text
    assert "sync" in response.text


def test_tasks_page_shows_empty_state_with_no_tasks(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_no_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/")

    assert response.status_code == 200
    assert "No tasks running right now." in response.text
    assert "No scheduled jobs." in response.text
    assert "No job runs recorded yet." in response.text


def test_tasks_page_lists_scheduled_jobs(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_scheduling_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/")

    assert response.status_code == 200
    assert "media_library_sync" in response.text
    assert "22:15:00" in response.text


def test_tasks_page_lists_job_history_with_status_and_error(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_scheduling_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/")

    assert response.status_code == 200
    assert "Failed" in response.text
    assert "connection refused" in response.text


def test_running_tasks_partial_lists_tasks(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "media_library_scan_fanout" in response.text


def test_running_tasks_partial_renders_progress_for_a_task_with_a_phase(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_with_progress_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "Translating to pt-BR (1/2)" in response.text
    assert 'value="1"' in response.text
    assert 'max="2"' in response.text


def test_running_tasks_partial_renders_no_progress_for_a_task_without_a_phase(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "<progress" not in response.text


def test_running_tasks_partial_shows_a_queued_badge_for_a_queued_task(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_queued_task_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "Queued" in response.text


def test_running_tasks_partial_shows_no_queued_badge_for_a_running_task(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "Queued" not in response.text


def test_running_tasks_partial_respects_the_limit_query_param(stub_backend_client):
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/system/tasks/running":
            return httpx.Response(200, json=[_TASK, _QUEUED_TASK])
        return httpx.Response(200, json=[])

    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running?limit=1")

    assert response.status_code == 200
    assert "media_library_scan_fanout" in response.text
    assert "subtitle_scan:2" not in response.text


def test_tasks_count_shows_badge_when_tasks_are_running(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/count")

    assert response.status_code == 200
    assert response.text.strip() == "1"


def test_tasks_count_is_empty_with_no_tasks(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_no_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/count")

    assert response.status_code == 200
    assert response.text.strip() == ""


def test_sidebar_links_to_the_tasks_page(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_no_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/")

    assert response.status_code == 200
    assert 'href="/system/tasks/"' in response.text


def test_topbar_notifications_bell_polls_the_same_running_tasks_endpoints(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_no_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/")

    assert response.status_code == 200
    assert 'id="notifications-toggle"' in response.text
    assert 'hx-get="/system/tasks/count"' in response.text
    assert 'hx-get="/system/tasks/running"' in response.text
