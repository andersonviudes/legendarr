from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app


def test_list_profiles_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/language-profiles/")

    assert response.status_code == 200
    assert response.json() == []
