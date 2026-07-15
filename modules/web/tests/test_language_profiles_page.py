from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def test_language_profiles_page_lists_no_profiles_by_default():
    with TestClient(create_app()) as client:
        response = client.get("/language-profiles/")

    assert response.status_code == 200
    assert "Nenhum perfil configurado" in response.text
