from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_dashboard_returns_ok():
    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "legendarr" in response.text
