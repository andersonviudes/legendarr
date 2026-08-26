import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_TASK = {
    "job_id": "media_library_scan_fanout",
    "name": "media_library_scan_fanout",
    "queue": "sync",
    "started_at": "2026-08-24T10:15:30.123456",
}


def _tasks_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[_TASK])


def _no_tasks_handler(request: httpx.Request) -> httpx.Response:
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


def test_running_tasks_partial_lists_tasks(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/running")

    assert response.status_code == 200
    assert "media_library_scan_fanout" in response.text


def test_tasks_count_shows_badge_when_tasks_are_running(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_tasks_handler)

    with TestClient(app) as client:
        response = client.get("/system/tasks/count")

    assert response.status_code == 200
    assert ">1<" in response.text


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
