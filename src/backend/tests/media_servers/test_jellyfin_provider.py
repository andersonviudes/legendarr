from pathlib import Path

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.media_servers.providers.jellyfin import JellyfinMediaServerProvider


def _provider() -> JellyfinMediaServerProvider:
    return JellyfinMediaServerProvider("http://jellyfin.local:8096", "tok")


def test_notify_subtitle_written_reports_the_video_path(monkeypatch):
    calls = []

    def _request(self, method, path, **kwargs):
        calls.append((method, path, kwargs))
        return httpx.Response(200)

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))

    assert len(calls) == 1
    method, path, kwargs = calls[0]
    assert method == "POST"
    assert path == "/Library/Media/Updated"
    assert kwargs["json"] == {
        "Updates": [{"Path": "/movies/Foo/Foo.mkv", "UpdateType": "Modified"}]
    }


def test_notify_subtitle_written_falls_back_to_full_refresh_on_failure(monkeypatch):
    responses = [httpx.Response(500), httpx.Response(200)]
    calls = []

    def _request(self, method, path, **kwargs):
        calls.append(path)
        return responses.pop(0)

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))

    assert calls == ["/Library/Media/Updated", "/Library/Refresh"]


def test_notify_subtitle_written_raises_when_fallback_also_fails(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "request", lambda self, method, path, **kwargs: httpx.Response(500)
    )

    with pytest.raises(ProviderClientError):
        _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))
