import io
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.legendas_net import LegendasNetProvider

_MOVIE_SEARCH_RESPONSE = {
    "success": True,
    "movies": [
        {
            "id": 111,
            "tmdb_id": 222,
            "path": "/download/movie/111.zip",
            "release_name": "Movie.Name.2024.WEB-DL",
            "uploader": "someone",
        }
    ],
}

_TV_SEARCH_RESPONSE = {
    "success": True,
    "tv_shows": [
        {
            "id": 333,
            "tmdb_id": 444,
            "path": "/download/tv/333.zip",
            "release_name": "Foo.Show.S01E02.HDTV",
            "uploader": "someone",
            "season": 1,
            "episode": 2,
        }
    ],
}


def _config(**overrides) -> SubtitleProviderConfig:
    data = {
        "kind": "legendas_net",
        "enabled": True,
        "username": "user@example.com",
        "password": "pass",
    }
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _login_post_json(self, path, json):
    assert path == "/v1/login"
    assert json == {"email": "user@example.com", "password": "pass"}
    return {"access_token": "token123"}


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_legendas_net_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unsupported language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    provider = LegendasNetProvider(_config())

    assert provider.search("Movie Name", "en", imdb_id="tt1234567") == []


def test_legendas_net_search_returns_empty_list_with_no_imdb_id_or_episode(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made with no movie/series signal")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    provider = LegendasNetProvider(_config())

    assert provider.search("Some Show", "pt-BR") == []


def test_legendas_net_search_raises_when_login_fails(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", lambda self, path, json: {"error": "nope"})

    provider = LegendasNetProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")


def test_legendas_net_search_returns_matching_movie_subtitle(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        assert method == "GET"
        assert path == "/v1/search/movie"
        assert json == {"name": "Movie Name", "page": 1, "per_page": 25, "imdb_id": "tt1234567"}
        assert headers == {"Authorization": "Bearer token123"}
        return httpx.Response(
            200, json=_MOVIE_SEARCH_RESPONSE, request=httpx.Request(method, "https://x" + path)
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())
    results = provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")

    assert len(results) == 1
    assert results[0].download_id == "/download/movie/111.zip"
    assert results[0].language == "pt-BR"
    assert results[0].release_name == "Movie.Name.2024.WEB-DL"
    assert results[0].page_link == "https://legendas.net/legenda?movie_id=222&legenda_id=111"


def test_legendas_net_search_returns_matching_tv_subtitle(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        assert method == "GET"
        assert path == "/v1/search/tv"
        assert json == {
            "name": "Foo Show",
            "page": 1,
            "per_page": 25,
            "tv_season": 1,
            "tv_episode": 2,
        }
        assert headers == {"Authorization": "Bearer token123"}
        return httpx.Response(
            200, json=_TV_SEARCH_RESPONSE, request=httpx.Request(method, "https://x" + path)
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())
    results = provider.search("Foo Show", "pt-BR", season=1, episode=2)

    assert len(results) == 1
    assert results[0].download_id == "/download/tv/333.zip"
    assert results[0].release_name == "Foo.Show.S01E02.HDTV"
    assert results[0].page_link == "https://legendas.net/tv_legenda?movie_id=444&legenda_id=333"


def test_legendas_net_search_returns_empty_list_when_no_results(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200,
            json={"success": True, "movies": []},
            request=httpx.Request(method, "https://x" + path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())

    assert provider.search("Movie Name", "pt-BR", imdb_id="tt1234567") == []


def test_legendas_net_search_raises_when_it_fails(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(500, request=httpx.Request(method, "https://x" + path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")


def test_legendas_net_download_sends_authorization_and_returns_subtitle_text(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    seen = {}

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        seen["path"] = path
        seen["headers"] = headers
        content = _zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n")
        return httpx.Response(200, content=content, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo", download_id="/download/movie/111.zip", language="pt-BR"
        )
    )

    assert "Hi" in result
    assert seen["path"] == "https://legendas.net/download/movie/111.zip"
    assert seen["headers"] == {"Authorization": "Bearer token123"}


def test_legendas_net_download_falls_back_to_raw_text_when_not_zipped(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200,
            content=b"1\n00:00:00,000 --> 00:00:01,000\nHi\n\n",
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo", download_id="/download/movie/111.zip", language="pt-BR"
        )
    )

    assert "Hi" in result


def test_legendas_net_download_raises_when_it_fails(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Foo", download_id="/download/movie/111.zip", language="pt-BR"
            )
        )


def test_legendas_net_reuses_the_same_client_and_session_across_calls(monkeypatch):
    login_calls = []

    def _post_json(self, path, json):
        login_calls.append(path)
        return {"access_token": "token123"}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, json=_MOVIE_SEARCH_RESPONSE, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = LegendasNetProvider(_config())
    provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")
    provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")

    assert len(login_calls) == 1


def test_legendas_net_close_closes_the_client(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    closed = {"called": False}

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, json=_MOVIE_SEARCH_RESPONSE, request=httpx.Request(method, path))

    def _close(self):
        closed["called"] = True

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", _close)

    provider = LegendasNetProvider(_config())
    assert closed["called"] is False

    provider.search("Movie Name", "pt-BR", imdb_id="tt1234567")
    provider.close()

    assert closed["called"] is True
