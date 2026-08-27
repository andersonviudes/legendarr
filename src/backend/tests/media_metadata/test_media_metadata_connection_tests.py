import httpx
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.media_metadata.connection_tests import (
    test_connection as check_connection,
)
from legendarr_backend.media_metadata.models import MetadataProviderConfig


def _config(**overrides) -> MetadataProviderConfig:
    data = {"kind": "tvdb", "enabled": True}
    data.update(overrides)
    return MetadataProviderConfig(**data)


def test_unknown_kind_fails():
    success, message = check_connection(_config(kind="not-a-real-provider"))

    assert success is False
    assert "Unknown metadata provider kind" in message


def test_tvdb_requires_api_key():
    success, message = check_connection(_config(kind="tvdb", api_key=None))

    assert success is False
    assert "API Key" in message


def test_tvdb_succeeds(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "post_json", lambda self, path, json: {"data": {"token": "tok"}}
    )
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: {"data": {"overview": "A show", "image": None, "year": "1994"}},
    )

    success, message = check_connection(_config(kind="tvdb", api_key="a-key"))

    assert success is True


def test_tvdb_reports_rejected_key(monkeypatch):
    def _raise(self, path, json):
        request = httpx.Request("POST", "https://api4.thetvdb.com/v4/login")
        response = httpx.Response(401, request=request)
        cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        raise ProviderClientError("failed with 401") from cause

    monkeypatch.setattr(ProviderHttpClient, "post_json", _raise)

    success, message = check_connection(_config(kind="tvdb", api_key="bad-key"))

    assert success is False
    assert "API Key" in message


def test_imdb_requires_api_key():
    success, message = check_connection(_config(kind="imdb", api_key=None))

    assert success is False
    assert "API Key" in message


def test_imdb_succeeds(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: {
            "Response": "True",
            "Plot": "A story",
            "Poster": "N/A",
            "Year": "1994",
            "imdbRating": "9.3",
        },
    )

    success, message = check_connection(_config(kind="imdb", api_key="a-key"))

    assert success is True


def test_imdb_reports_rejected_key(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: {"Response": "False", "Error": "Invalid API key!"},
    )

    success, message = check_connection(_config(kind="imdb", api_key="bad-key"))

    assert success is False
    assert "API Key" in message


def test_tmdb_requires_api_key():
    success, message = check_connection(_config(kind="tmdb", api_key=None))

    assert success is False
    assert "API Key" in message


def test_tmdb_succeeds(monkeypatch):
    def _get_json(self, path):
        if path.startswith("/find/"):
            return {"movie_results": [{"id": 278}]}
        return {"overview": "A story", "poster_path": None, "release_date": "1994-09-23"}

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    success, message = check_connection(_config(kind="tmdb", api_key="a-key"))

    assert success is True


def test_tmdb_reports_failure_when_lookup_finds_nothing(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"movie_results": []})

    success, message = check_connection(_config(kind="tmdb", api_key="a-key"))

    assert success is False
    assert "returned nothing" in message


def test_tmdb_reports_rejected_key(monkeypatch):
    def _raise(self, path):
        request = httpx.Request("GET", "https://api.themoviedb.org/3/find/tt0111161")
        response = httpx.Response(401, request=request)
        cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        raise ProviderClientError("failed with 401") from cause

    monkeypatch.setattr(ProviderHttpClient, "get_json", _raise)

    success, message = check_connection(_config(kind="tmdb", api_key="bad-key"))

    assert success is False
    assert "API Key" in message
