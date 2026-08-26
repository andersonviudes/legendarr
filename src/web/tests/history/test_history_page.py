from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_history_page_returns_ok(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/history/")

    assert response.status_code == 200
