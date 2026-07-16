from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_history_page_returns_ok():
    with TestClient(create_app()) as client:
        response = client.get("/history/")

    assert response.status_code == 200
