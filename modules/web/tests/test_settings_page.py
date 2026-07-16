import httpx
from fastapi.testclient import TestClient
from legendarr_backend.shared_kernel.api import create_api_app
from legendarr_web.app import create_app
from legendarr_web.shared_kernel.backend_client import get_backend_client


def test_settings_page_lists_no_profiles_by_default():
    app = create_app()
    app.dependency_overrides[get_backend_client] = lambda: httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_api_app()), base_url="http://backend/"
    )

    with TestClient(app) as client:
        response = client.get("/settings/")

    assert response.status_code == 200
    assert "No profile configured" in response.text
