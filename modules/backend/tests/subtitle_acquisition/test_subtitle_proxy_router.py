import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient


@pytest.fixture
def reachable_proxy(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path="/": None)


def _payload(**overrides) -> dict:
    data = {"name": "FlareSolverr", "host": "http://10.0.1.1:8191/", "enabled": True}
    data.update(overrides)
    return data


def test_list_proxies_returns_empty_list_on_fresh_db(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/subtitle-proxies/")

    assert response.status_code == 200
    assert response.json() == []


def test_create_get_update_delete_proxy(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        created = client.post("/subtitle-proxies/", json=_payload())
        assert created.status_code == 201
        proxy_id = created.json()["id"]

        get_response = client.get(f"/subtitle-proxies/{proxy_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "FlareSolverr"

        update_response = client.put(
            f"/subtitle-proxies/{proxy_id}", json=_payload(host="http://10.0.1.2:8191/")
        )
        assert update_response.status_code == 200
        assert update_response.json()["host"] == "http://10.0.1.2:8191/"

        delete_response = client.delete(f"/subtitle-proxies/{proxy_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/subtitle-proxies/{proxy_id}")
        assert missing_response.status_code == 404


def test_get_update_delete_return_404_when_missing(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        assert client.get("/subtitle-proxies/1").status_code == 404
        assert client.put("/subtitle-proxies/1", json=_payload()).status_code == 404
        assert client.delete("/subtitle-proxies/1").status_code == 404


def test_toggle_enabled_flips_flag(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        proxy_id = client.post("/subtitle-proxies/", json=_payload(enabled=True)).json()["id"]

        disabled = client.patch(f"/subtitle-proxies/{proxy_id}/enabled", json={"enabled": False})
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        enabled = client.patch(f"/subtitle-proxies/{proxy_id}/enabled", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is True


def test_toggle_enabled_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.patch("/subtitle-proxies/1/enabled", json={"enabled": True})
        assert response.status_code == 404


def test_create_returns_409_on_duplicate_name(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        assert client.post("/subtitle-proxies/", json=_payload()).status_code == 201

        response = client.post("/subtitle-proxies/", json=_payload())

        assert response.status_code == 409


def test_update_returns_409_on_duplicate_name(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        client.post("/subtitle-proxies/", json=_payload())
        other = client.post("/subtitle-proxies/", json=_payload(name="FlareSolverr 2"))
        other_id = other.json()["id"]

        response = client.put(f"/subtitle-proxies/{other_id}", json=_payload(name="FlareSolverr"))

        assert response.status_code == 409


def test_create_rejects_unreachable_proxy(isolated_database, monkeypatch):
    def _raise(self, path="/"):
        raise ProviderClientError("FlareSolverr request to http://10.0.1.1:8191 failed: boom")

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    with TestClient(create_api_app()) as client:
        response = client.post("/subtitle-proxies/", json=_payload())
        assert response.status_code == 422
        assert "boom" in response.json()["detail"]
        # nothing was persisted
        assert client.get("/subtitle-proxies/").json() == []


def test_update_rejects_unreachable_proxy(isolated_database, monkeypatch, reachable_proxy):
    with TestClient(create_api_app()) as client:
        proxy_id = client.post("/subtitle-proxies/", json=_payload()).json()["id"]

        def _raise(self, path="/"):
            raise ProviderClientError("FlareSolverr request to http://10.0.1.1:8191 failed: boom")

        monkeypatch.setattr(ProviderHttpClient, "ping", _raise)
        response = client.put(
            f"/subtitle-proxies/{proxy_id}", json=_payload(host="http://10.0.1.2:8191/")
        )

        assert response.status_code == 422
        assert "boom" in response.json()["detail"]
        # the stored host was not overwritten
        assert client.get(f"/subtitle-proxies/{proxy_id}").json()["host"] == "http://10.0.1.1:8191/"


def test_test_connection_returns_success(isolated_database, reachable_proxy):
    with TestClient(create_api_app()) as client:
        response = client.post("/subtitle-proxies/test", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Connection successful"}


def test_test_connection_returns_failure_message(isolated_database, monkeypatch):
    def _raise(self, path="/"):
        raise ProviderClientError("boom")

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    with TestClient(create_api_app()) as client:
        response = client.post("/subtitle-proxies/test", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"success": False, "message": "boom"}
