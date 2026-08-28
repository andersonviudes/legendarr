import json
from io import BytesIO
from zipfile import ZipFile

import pytest
import yaml
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.backup import router as backup_router
from legendarr_backend.backup.manage_backups import CONFIG_NAME, MANIFEST_NAME
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.config.settings import Settings


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """A TestClient whose backup router reads/writes `data_dir/backups` under `tmp_path`."""
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(backup_router, "get_settings", lambda: settings)
    return TestClient(create_api_app())


def _valid_archive_bytes(public_url: str = "https://restored.example.com") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            MANIFEST_NAME,
            json.dumps({"created_at": "2026-08-28T00:00:00+00:00", "secret_key_included": False}),
        )
        config = AppConfigFile(public_url=public_url).model_dump()
        archive.writestr(CONFIG_NAME, yaml.safe_dump(config))
    return buffer.getvalue()


def test_list_backups_starts_empty(api_client):
    response = api_client.get("/backup/")

    assert response.status_code == 200
    assert response.json() == []


def test_create_backup_appears_in_the_list(api_client):
    create_response = api_client.post("/backup/")
    assert create_response.status_code == 201
    filename = create_response.json()["filename"]

    list_response = api_client.get("/backup/")

    assert [backup["filename"] for backup in list_response.json()] == [filename]


def test_download_backup_returns_the_archive_bytes(api_client, tmp_path):
    filename = api_client.post("/backup/").json()["filename"]

    response = api_client.get(f"/backup/{filename}/download")

    assert response.status_code == 200
    assert response.content == (tmp_path / "backups" / filename).read_bytes()


def test_download_backup_404_for_unknown_filename(api_client):
    response = api_client.get("/backup/not-a-backup.zip/download")

    assert response.status_code == 404


def test_delete_backup_removes_it(api_client):
    filename = api_client.post("/backup/").json()["filename"]

    response = api_client.delete(f"/backup/{filename}")

    assert response.status_code == 204
    assert api_client.get("/backup/").json() == []


def test_delete_backup_404_for_unknown_filename(api_client):
    response = api_client.delete("/backup/legendarr-backup-20260101T000000000000Z.zip")

    assert response.status_code == 404


def test_restore_endpoint_applies_the_uploaded_archive(api_client, tmp_path):
    archive_bytes = _valid_archive_bytes()

    response = api_client.post(
        "/backup/restore",
        files={"file": ("legendarr-backup-restore.zip", archive_bytes, "application/zip")},
    )

    assert response.status_code == 200
    assert "restart" in response.json()["message"].lower()
    stored = yaml.safe_load((tmp_path / "config.yaml").read_text())
    assert stored["public_url"] == "https://restored.example.com"


def test_restore_endpoint_rejects_an_invalid_archive(api_client):
    response = api_client.post(
        "/backup/restore",
        files={"file": ("not-a-backup.zip", b"not a zip file", "application/zip")},
    )

    assert response.status_code == 422
