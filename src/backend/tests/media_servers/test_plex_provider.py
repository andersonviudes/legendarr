from pathlib import Path

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.media_servers.providers.plex import PlexMediaServerProvider

_SECTIONS_BODY = {
    "MediaContainer": {
        "Directory": [
            {"key": "1", "type": "movie", "Location": [{"path": "/movies"}]},
            {"key": "2", "type": "show", "Location": [{"path": "/tv"}]},
        ]
    }
}


def _provider() -> PlexMediaServerProvider:
    return PlexMediaServerProvider("http://plex.local:32400", "tok")


def test_notify_subtitle_written_targets_the_matching_section(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _SECTIONS_BODY)
    calls = []

    def _request(self, method, path, **kwargs):
        calls.append((method, path))
        return httpx.Response(200)

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))

    assert len(calls) == 1
    method, path = calls[0]
    assert method == "GET"
    assert "/library/sections/1/refresh" in path
    assert "force=1" in path
    assert "path=" in path


def test_notify_subtitle_written_skips_when_no_section_matches(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _SECTIONS_BODY)
    calls = []
    monkeypatch.setattr(
        ProviderHttpClient,
        "request",
        lambda self, method, path, **kwargs: calls.append((method, path)),
    )

    _provider().notify_subtitle_written(Path("/unrelated/Foo/Foo.mkv"))

    assert calls == []


def test_notify_subtitle_written_falls_back_to_full_refresh_on_targeted_failure(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _SECTIONS_BODY)
    responses = [httpx.Response(500), httpx.Response(200)]

    def _request(self, method, path, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))

    assert responses == []


def test_notify_subtitle_written_raises_when_fallback_also_fails(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _SECTIONS_BODY)
    monkeypatch.setattr(
        ProviderHttpClient, "request", lambda self, method, path, **kwargs: httpx.Response(500)
    )

    with pytest.raises(ProviderClientError):
        _provider().notify_subtitle_written(Path("/movies/Foo/Foo.mkv"))
