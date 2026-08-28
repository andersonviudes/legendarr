import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_BACKUP = {
    "filename": "legendarr-backup-20260828T000000000000Z.zip",
    "created_at": "2026-08-28T00:00:00+00:00",
    "size_bytes": 1234,
    "secret_key_included": True,
}
_RETENTION = {"backup_retention_count": 7}


def _handler(backups=None, retention=None, overrides=None):
    backups = [] if backups is None else backups
    retention = _RETENTION if retention is None else retention
    overrides = {} if overrides is None else overrides

    def handler(request: httpx.Request) -> httpx.Response:
        for matcher, response_factory in overrides.items():
            method, path = matcher
            if request.method == method and request.url.path == path:
                return response_factory(request)
        if request.method == "GET" and request.url.path == "/backup/":
            return httpx.Response(200, json=backups)
        if request.method == "POST" and request.url.path == "/backup/":
            return httpx.Response(201, json=_BACKUP)
        if request.method == "GET" and request.url.path == "/settings/backup-retention":
            return httpx.Response(200, json=retention)
        if request.method == "PUT" and request.url.path == "/settings/backup-retention":
            return httpx.Response(200, json=json.loads(request.content))
        return httpx.Response(200, json=[])

    return handler


def test_backup_page_renders_the_list_and_retention(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler(backups=[_BACKUP]))

    with TestClient(app) as client:
        response = client.get("/settings/backup/")

    assert response.status_code == 200
    assert _BACKUP["filename"] in response.text
    assert 'value="7"' in response.text


def test_backup_page_renders_empty_state(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler(backups=[]))

    with TestClient(app) as client:
        response = client.get("/settings/backup/")

    assert response.status_code == 200
    assert "No backups yet." in response.text


def test_create_backup_redirects_with_toast(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler())

    with TestClient(app) as client:
        response = client.post("/settings/backup/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/settings/backup/?")
    assert "toast=Backup+created." in response.headers["location"]


def test_save_retention_redirects_with_toast(stub_backend_client):
    app = create_app()
    saved: dict = {}

    def put_retention(request: httpx.Request) -> httpx.Response:
        saved.update(json.loads(request.content))
        return httpx.Response(200, json=saved)

    stub_backend_client(
        app, handler=_handler(overrides={("PUT", "/settings/backup-retention"): put_retention})
    )

    with TestClient(app) as client:
        response = client.post(
            "/settings/backup/retention",
            data={"backup_retention_count": "3"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert saved == {"backup_retention_count": 3}
    assert "toast=Retention+setting+saved." in response.headers["location"]


def test_save_retention_renders_error_on_rejection(stub_backend_client):
    app = create_app()

    def put_retention(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Must be at least 1"})

    stub_backend_client(
        app, handler=_handler(overrides={("PUT", "/settings/backup-retention"): put_retention})
    )

    with TestClient(app) as client:
        response = client.post(
            "/settings/backup/retention",
            data={"backup_retention_count": "0"},
            follow_redirects=False,
        )

    assert response.status_code == 422
    assert "Must be at least 1" in response.text


def test_download_backup_returns_bytes_with_content_disposition(stub_backend_client):
    app = create_app()
    archive_bytes = b"PK\x03\x04fake-zip-bytes"

    def download(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=archive_bytes, headers={"content-type": "application/zip"}
        )

    stub_backend_client(
        app,
        handler=_handler(overrides={("GET", f"/backup/{_BACKUP['filename']}/download"): download}),
    )

    with TestClient(app) as client:
        response = client.get(f"/settings/backup/{_BACKUP['filename']}/download")

    assert response.status_code == 200
    assert response.content == archive_bytes
    assert _BACKUP["filename"] in response.headers["content-disposition"]


def test_download_backup_404_when_backend_404s(stub_backend_client):
    app = create_app()

    def download(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Backup not found"})

    stub_backend_client(
        app, handler=_handler(overrides={("GET", "/backup/missing.zip/download"): download})
    )

    with TestClient(app) as client:
        response = client.get("/settings/backup/missing.zip/download")

    assert response.status_code == 404


def test_delete_backup_via_htmx_returns_hx_redirect(stub_backend_client):
    app = create_app()

    def delete(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    stub_backend_client(
        app, handler=_handler(overrides={("DELETE", f"/backup/{_BACKUP['filename']}"): delete})
    )

    with TestClient(app) as client:
        response = client.post(
            f"/settings/backup/{_BACKUP['filename']}/delete",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.headers["hx-redirect"].startswith("/settings/backup/?")


def test_delete_backup_without_htmx_redirects_normally(stub_backend_client):
    app = create_app()

    def delete(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    stub_backend_client(
        app, handler=_handler(overrides={("DELETE", f"/backup/{_BACKUP['filename']}"): delete})
    )

    with TestClient(app) as client:
        response = client.post(
            f"/settings/backup/{_BACKUP['filename']}/delete", follow_redirects=False
        )

    assert response.status_code == 303
    assert "toast=Backup+deleted." in response.headers["location"]


def test_restore_returns_success_message(stub_backend_client):
    app = create_app()

    def restore(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": "Restore complete. Restart legendarr."})

    stub_backend_client(app, handler=_handler(overrides={("POST", "/backup/restore"): restore}))

    with TestClient(app) as client:
        response = client.post(
            "/settings/backup/restore",
            files={"file": ("legendarr-backup-restore.zip", b"fake zip bytes", "application/zip")},
        )

    assert response.status_code == 200
    assert "Restart legendarr" in response.text


def test_restore_renders_error_on_rejection(stub_backend_client):
    app = create_app()

    def restore(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "Not a valid backup archive."})

    stub_backend_client(app, handler=_handler(overrides={("POST", "/backup/restore"): restore}))

    with TestClient(app) as client:
        response = client.post(
            "/settings/backup/restore",
            files={"file": ("not-a-backup.zip", b"garbage", "application/zip")},
        )

    assert response.status_code == 422
    assert "Not a valid backup archive." in response.text
