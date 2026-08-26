import httpx
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.media_servers.connection_tests import test_connection as check_connection
from legendarr_backend.media_servers.models import MediaServerConfig


def _config(**overrides) -> MediaServerConfig:
    data = {"kind": "plex", "enabled": True}
    data.update(overrides)
    return MediaServerConfig(**data)


def test_unknown_kind_fails():
    success, message = check_connection(_config(kind="not-a-real-server"))

    assert success is False
    assert "Unknown media server kind" in message


def test_plex_requires_base_url():
    success, message = check_connection(_config(kind="plex", base_url=None, token="tok"))

    assert success is False
    assert "base URL" in message


def test_plex_requires_token():
    success, message = check_connection(
        _config(kind="plex", base_url="http://plex.local:32400", token=None)
    )

    assert success is False
    assert "Plex token" in message


def test_plex_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path: None)

    success, message = check_connection(
        _config(kind="plex", base_url="http://plex.local:32400", token="tok")
    )

    assert success is True


def test_plex_reports_rejected_token(monkeypatch):
    def _raise(self, path):
        request = httpx.Request("GET", "http://plex.local:32400/library/sections")
        response = httpx.Response(401, request=request)
        cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        raise ProviderClientError("failed with 401") from cause

    monkeypatch.setattr(ProviderHttpClient, "ping", _raise)

    success, message = check_connection(
        _config(kind="plex", base_url="http://plex.local:32400", token="bad-token")
    )

    assert success is False
    assert "API Key" in message


def test_jellyfin_requires_base_url():
    success, message = check_connection(_config(kind="jellyfin", base_url=None, token="tok"))

    assert success is False
    assert "base URL" in message


def test_jellyfin_requires_token():
    success, message = check_connection(
        _config(kind="jellyfin", base_url="http://jellyfin.local:8096", token=None)
    )

    assert success is False
    assert "Jellyfin API key" in message


def test_jellyfin_succeeds(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "ping", lambda self, path: None)

    success, message = check_connection(
        _config(kind="jellyfin", base_url="http://jellyfin.local:8096", token="tok")
    )

    assert success is True
