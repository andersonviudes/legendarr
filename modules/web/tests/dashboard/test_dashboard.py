import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app
from legendarr_web.backend_client.client import get_backend_client


def _empty_profiles_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def test_dashboard_returns_ok():
    app = create_app()
    app.dependency_overrides[get_backend_client] = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(_empty_profiles_handler), base_url="http://backend/"
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "legendarr" in response.text
