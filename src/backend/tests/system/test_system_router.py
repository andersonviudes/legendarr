import logging

from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.logging.setup import configure_logging


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
