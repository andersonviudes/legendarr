from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app


def _payload(**overrides) -> dict:
    data = {
        "name": "anime",
        "source_languages": "ja",
        "target_languages": "pt-BR,en",
        "extract_embedded_subtitles": True,
        "forced": False,
        "hearing_impaired": False,
        "is_default": False,
    }
    data.update(overrides)
    return data


def test_list_profiles_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/language-profiles/")

    assert response.status_code == 200
    assert response.json() == []


def test_create_get_update_delete_profile(isolated_database):
    with TestClient(create_api_app()) as client:
        created = client.post("/language-profiles/", json=_payload())
        assert created.status_code == 201
        profile_id = created.json()["id"]

        get_response = client.get(f"/language-profiles/{profile_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "anime"

        update_response = client.put(
            f"/language-profiles/{profile_id}", json=_payload(target_languages="pt-BR")
        )
        assert update_response.status_code == 200
        assert update_response.json()["target_languages"] == "pt-BR"

        delete_response = client.delete(f"/language-profiles/{profile_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/language-profiles/{profile_id}")
        assert missing_response.status_code == 404


def test_get_update_delete_return_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/language-profiles/1").status_code == 404
        assert client.put("/language-profiles/1", json=_payload()).status_code == 404
        assert client.delete("/language-profiles/1").status_code == 404


def test_create_returns_409_on_duplicate_name(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.post("/language-profiles/", json=_payload()).status_code == 201

        response = client.post("/language-profiles/", json=_payload())

        assert response.status_code == 409


def test_update_returns_409_on_duplicate_name(isolated_database):
    with TestClient(create_api_app()) as client:
        client.post("/language-profiles/", json=_payload())
        other = client.post("/language-profiles/", json=_payload(name="live-action")).json()

        response = client.put(f"/language-profiles/{other['id']}", json=_payload(name="anime"))

        assert response.status_code == 409


def test_create_returns_422_on_blank_name(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post("/language-profiles/", json=_payload(name=""))

    assert response.status_code == 422
