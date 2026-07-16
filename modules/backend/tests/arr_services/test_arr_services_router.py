from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.http_client.client import ProviderHttpClient


def _payload(**overrides) -> dict:
    data = {
        "name": "radarr",
        "service_type": "radarr",
        "enabled": True,
        "host": "radarr",
        "port": 7878,
        "base_url": "/",
        "use_ssl": False,
        "http_timeout_seconds": 60,
        "api_key": "api-key",
    }
    data.update(overrides)
    return data


def test_list_services_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/arr-services/")

    assert response.status_code == 200
    assert response.json() == []


def test_create_get_update_delete_service(isolated_database):
    with TestClient(create_api_app()) as client:
        created = client.post("/arr-services/", json=_payload())
        assert created.status_code == 201
        service_id = created.json()["id"]

        get_response = client.get(f"/arr-services/{service_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "radarr"

        update_response = client.put(
            f"/arr-services/{service_id}", json=_payload(host="radarr.internal")
        )
        assert update_response.status_code == 200
        assert update_response.json()["host"] == "radarr.internal"

        delete_response = client.delete(f"/arr-services/{service_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/arr-services/{service_id}")
        assert missing_response.status_code == 404


def test_get_update_delete_return_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.get("/arr-services/1").status_code == 404
        assert client.put("/arr-services/1", json=_payload()).status_code == 404
        assert client.delete("/arr-services/1").status_code == 404


def test_create_returns_409_on_duplicate_name(isolated_database):
    with TestClient(create_api_app()) as client:
        assert client.post("/arr-services/", json=_payload()).status_code == 201

        response = client.post("/arr-services/", json=_payload())

        assert response.status_code == 409


def test_update_returns_409_on_duplicate_name(isolated_database):
    with TestClient(create_api_app()) as client:
        client.post("/arr-services/", json=_payload())
        other = client.post("/arr-services/", json=_payload(name="sonarr", service_type="sonarr"))
        other_id = other.json()["id"]

        response = client.put(f"/arr-services/{other_id}", json=_payload(name="radarr"))

        assert response.status_code == 409


def test_create_returns_422_on_invalid_port(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/", json=_payload(port=-1))

    assert response.status_code == 422


def test_list_services_omits_api_key(isolated_database):
    with TestClient(create_api_app()) as client:
        client.post("/arr-services/", json=_payload())

        response = client.get("/arr-services/")

    assert "api_key" not in response.json()[0]


def test_test_connection_returns_success(isolated_database, monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"version": "1.0"})

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/test", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Connection successful"}


def test_test_connection_returns_failure_message(isolated_database, monkeypatch):
    def _raise(self, path):
        from legendarr_backend.http_client.client import ProviderClientError

        raise ProviderClientError("Radarr request to http://radarr failed: boom")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/test", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "boom" in body["message"]
