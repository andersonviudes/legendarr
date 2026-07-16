import httpx
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_web.app import create_app
from legendarr_web.backend_client.client import get_backend_client


def test_dashboard_returns_ok():
    app = create_app()
    app.dependency_overrides[get_backend_client] = lambda: httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_api_app()), base_url="http://backend/"
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "legendarr" in response.text
