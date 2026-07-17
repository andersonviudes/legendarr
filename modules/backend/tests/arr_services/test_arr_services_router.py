import httpx
import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_clients.radarr_client import RadarrClient
from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient


@pytest.fixture
def reachable_server(monkeypatch):
    """Make each arr report itself as its own app so create/update pass the connection check."""
    monkeypatch.setattr(
        RadarrClient, "system_status", lambda self: {"appName": "Radarr", "version": "5.0"}
    )
    monkeypatch.setattr(
        SonarrClient, "system_status", lambda self: {"appName": "Sonarr", "version": "4.0"}
    )


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


def test_create_get_update_delete_service(isolated_database, reachable_server):
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


def test_get_update_delete_return_404_when_missing(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        assert client.get("/arr-services/1").status_code == 404
        assert client.put("/arr-services/1", json=_payload()).status_code == 404
        assert client.delete("/arr-services/1").status_code == 404


def test_toggle_enabled_flips_flag(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        service_id = client.post("/arr-services/", json=_payload(enabled=True)).json()["id"]

        disabled = client.patch(f"/arr-services/{service_id}/enabled", json={"enabled": False})
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        enabled = client.patch(f"/arr-services/{service_id}/enabled", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True


def test_toggle_enabled_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/arr-services/1/enabled", json={"enabled": True})
        assert response.status_code == 404


def test_create_returns_409_on_duplicate_name(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        assert client.post("/arr-services/", json=_payload()).status_code == 201

        response = client.post("/arr-services/", json=_payload())

        assert response.status_code == 409


def test_update_returns_409_on_duplicate_name(isolated_database, reachable_server):
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


def test_create_rejects_unreachable_server(isolated_database, monkeypatch):
    def _raise(self, path):
        raise ProviderClientError("Radarr request to http://radarr failed: boom")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/", json=_payload())
        assert response.status_code == 422
        assert "boom" in response.json()["detail"]
        # nothing was persisted
        assert client.get("/arr-services/").json() == []


def test_create_rejects_wrong_app_type(isolated_database, monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", lambda self, path: {"appName": "Sonarr", "version": "4.0"}
    )

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/", json=_payload(service_type="radarr"))
        assert response.status_code == 422
        assert "Sonarr" in response.json()["detail"]
        assert client.get("/arr-services/").json() == []


def test_update_rejects_unreachable_server(isolated_database, monkeypatch):
    with TestClient(create_api_app()) as client:
        monkeypatch.setattr(
            ProviderHttpClient, "get_json", lambda self, path: {"appName": "Radarr"}
        )
        service_id = client.post("/arr-services/", json=_payload()).json()["id"]

        def _raise(self, path):
            raise ProviderClientError("Radarr request to http://radarr failed: boom")

        monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)
        response = client.put(f"/arr-services/{service_id}", json=_payload(host="radarr.internal"))

        assert response.status_code == 422
        assert "boom" in response.json()["detail"]
        # the stored host was not overwritten
        assert client.get(f"/arr-services/{service_id}").json()["host"] == "radarr"


def test_list_services_omits_api_key(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        client.post("/arr-services/", json=_payload())

        response = client.get("/arr-services/")

    assert "api_key" not in response.json()[0]


def test_create_and_get_omit_api_key(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        created = client.post("/arr-services/", json=_payload())
        assert "api_key" not in created.json()

        fetched = client.get(f"/arr-services/{created.json()['id']}")
        assert "api_key" not in fetched.json()


def test_create_rejects_empty_api_key(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/", json=_payload(api_key=""))

    assert response.status_code == 422
    assert "API Key" in response.json()["detail"]


def test_update_with_blank_api_key_keeps_existing(isolated_database, reachable_server):
    with TestClient(create_api_app()) as client:
        service_id = client.post("/arr-services/", json=_payload(api_key="original-key")).json()[
            "id"
        ]

        updated = client.put(
            f"/arr-services/{service_id}", json=_payload(host="radarr.internal", api_key="")
        )
        assert updated.status_code == 200
        assert updated.json()["host"] == "radarr.internal"

    # api_key isn't returned over the wire, so assert the stored value directly
    from legendarr_backend.arr_services.manage_arr_service import get_arr_service
    from legendarr_backend.database.engine import get_session

    with get_session() as session:
        assert get_arr_service(session, service_id).api_key == "original-key"


def test_update_rejects_wrong_app_type(isolated_database, monkeypatch):
    def _status(self):
        return {"appName": "Radarr", "version": "5.0"}

    monkeypatch.setattr(RadarrClient, "system_status", _status)
    monkeypatch.setattr(SonarrClient, "system_status", _status)

    with TestClient(create_api_app()) as client:
        service_id = client.post("/arr-services/", json=_payload()).json()["id"]

        # now the box answers as a Sonarr while the config still says radarr
        monkeypatch.setattr(
            RadarrClient, "system_status", lambda self: {"appName": "Sonarr", "version": "4.0"}
        )
        response = client.put(f"/arr-services/{service_id}", json=_payload(host="radarr.internal"))

    assert response.status_code == 422
    assert "Sonarr" in response.json()["detail"]


def test_test_connection_returns_success(isolated_database, monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", lambda self, path: {"appName": "Radarr", "version": "5.0"}
    )

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/test", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "Radarr" in body["message"]
    assert "5.0" in body["message"]


def test_test_connection_reports_rejected_api_key(isolated_database, monkeypatch):
    def _raise_401(self, path):
        request = httpx.Request("GET", "http://radarr/api/v3/system/status")
        response = httpx.Response(401, request=request)
        cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        raise ProviderClientError("Radarr request failed with 401") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise_401)

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/test", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "API Key" in body["message"]


def test_test_connection_reports_wrong_app_type(isolated_database, monkeypatch):
    # a Sonarr instance answering behind a Radarr config
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", lambda self, path: {"appName": "Sonarr", "version": "4.0"}
    )

    with TestClient(create_api_app()) as client:
        response = client.post("/arr-services/test", json=_payload(service_type="radarr"))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "Sonarr" in body["message"]
    assert "Radarr" in body["message"]


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
