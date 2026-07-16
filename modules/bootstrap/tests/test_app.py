from fastapi.testclient import TestClient
from legendarr_bootstrap.app import create_app


def test_dashboard_and_api_are_both_mounted():
    with TestClient(create_app()) as client:
        dashboard_response = client.get("/")
        api_response = client.get("/api/language-profiles/")

    assert dashboard_response.status_code == 200
    assert api_response.status_code == 200
    assert api_response.json() == []
