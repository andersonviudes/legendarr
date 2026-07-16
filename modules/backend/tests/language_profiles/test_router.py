from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.config.settings import Settings
from legendarr_backend.database import engine as database


def test_list_profiles_returns_empty_list_on_fresh_db(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, database_url="")
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "_engine", None)

    with TestClient(create_api_app()) as client:
        response = client.get("/language-profiles/")

    assert response.status_code == 200
    assert response.json() == []
