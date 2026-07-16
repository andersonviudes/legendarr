from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_settings_page_lists_no_profiles_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app)

    with TestClient(app) as client:
        response = client.get("/settings/")

    assert response.status_code == 200
    assert "No profile configured" in response.text
