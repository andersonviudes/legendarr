import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import OpenSubtitlesProvider


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "opensubtitles", "enabled": True, "username": "user", "password": "pass"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _search_response(**overrides) -> dict:
    data = {
        "data": [
            {
                "attributes": {
                    "release": "Movie.Name.2024.1080p.WEB-DL",
                    "language": "en",
                    "files": [{"file_id": 123}],
                }
            }
        ]
    }
    data.update(overrides)
    return data


def _login_post_json(self, path, json):
    assert path == "/api/v1/login"
    assert json == {"username": "user", "password": "pass"}
    return {"token": "token123", "base_url": "api.opensubtitles.com"}


def test_opensubtitles_search_returns_one_result_per_file(monkeypatch):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(_config())
    results = provider.search("Movie Name", "en")

    assert len(results) == 1
    assert results[0].release_name == "Movie.Name.2024.1080p.WEB-DL"
    assert results[0].download_id == "123"
    assert results[0].language == "en"
    assert seen["path"].startswith("/api/v1/subtitles?")
    assert "query=Movie" in seen["path"]
    assert "ai_translated=exclude" in seen["path"]
    assert "machine_translated=exclude" in seen["path"]


def test_opensubtitles_search_includes_optional_ai_and_machine_translated(monkeypatch):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(
        _config(include_ai_translated=True, include_machine_translated=True)
    )
    provider.search("Movie Name", "en")

    assert "ai_translated=include" in seen["path"]
    assert "machine_translated=include" in seen["path"]


def test_opensubtitles_search_passes_imdb_id_and_moviehash_when_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(_config())
    provider.search("Movie Name", "en", imdb_id="tt1234567", moviehash="abc123")

    assert "imdb_id=1234567" in seen["path"]
    assert "moviehash=abc123" in seen["path"]


def test_opensubtitles_search_uses_parent_imdb_id_and_episode_numbers_for_a_series(monkeypatch):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(_config())
    provider.search(
        "Ahsoka", "pt-br", imdb_id=None, series_imdb_id="tt13622776", season=1, episode=4
    )

    assert "parent_imdb_id=13622776" in seen["path"]
    assert "season_number=1" in seen["path"]
    assert "episode_number=4" in seen["path"]
    assert "query=" not in seen["path"]
    assert "&imdb_id=" not in seen["path"]


def test_opensubtitles_search_falls_back_to_query_and_episode_numbers_without_series_imdb_id(
    monkeypatch,
):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(_config())
    provider.search("Ahsoka", "pt-br", season=1, episode=4)

    assert "query=Ahsoka" in seen["path"]
    assert "season_number=1" in seen["path"]
    assert "episode_number=4" in seen["path"]
    assert "parent_imdb_id" not in seen["path"]


def test_opensubtitles_search_ignores_moviehash_when_use_hash_is_disabled(monkeypatch):
    seen = {}
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = OpenSubtitlesProvider(_config(use_hash=False))
    provider.search("Movie Name", "en", moviehash="abc123")

    assert "moviehash" not in seen["path"]


def test_opensubtitles_search_reads_hash_match_and_hearing_impaired(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: _search_response(
            data=[
                {
                    "attributes": {
                        "release": "Movie.Name.2024.1080p.WEB-DL",
                        "language": "en",
                        "moviehash_match": True,
                        "hearing_impaired": True,
                        "files": [{"file_id": 123}],
                    }
                }
            ]
        ),
    )

    provider = OpenSubtitlesProvider(_config())
    results = provider.search("Movie Name", "en")

    assert results[0].hash_matched is True
    assert results[0].hearing_impaired is True


def test_opensubtitles_search_defaults_hash_match_and_hearing_impaired_to_false(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: _search_response())

    provider = OpenSubtitlesProvider(_config())
    results = provider.search("Movie Name", "en")

    assert results[0].hash_matched is False
    assert results[0].hearing_impaired is False


def test_opensubtitles_search_returns_empty_list_when_no_results(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})

    provider = OpenSubtitlesProvider(_config())

    assert provider.search("Movie Name", "en") == []


def test_opensubtitles_search_raises_when_login_fails(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", lambda self, path, json: {"error": "no"})

    provider = OpenSubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.search("Movie Name", "en")


def test_opensubtitles_search_routes_a_vip_account_to_its_own_host(monkeypatch):
    seen: dict = {"base_urls": []}
    original_init = ProviderHttpClient.__init__

    def _init(self, provider, base_url, headers=None, timeout=10.0):
        seen["base_urls"].append(base_url)
        seen["headers"] = headers
        original_init(self, provider, base_url, headers=headers, timeout=timeout)

    monkeypatch.setattr(ProviderHttpClient, "__init__", _init)
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {"token": "token123", "base_url": "vip-api.opensubtitles.com"},
    )
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config())
    provider.search("Movie Name", "en")

    assert seen["base_urls"] == [
        "https://api.opensubtitles.com",
        "https://vip-api.opensubtitles.com",
    ]
    assert seen["headers"]["Authorization"] == "Bearer token123"


def test_opensubtitles_download_fetches_link_then_returns_its_text(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
        if path == "/api/v1/login":
            return _login_post_json(self, path, json)
        seen["download_request"] = (path, json)
        return {"link": "https://example.com/download/abc.srt"}

    class _Response:
        is_success = True
        text = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"

    def _request(self, method, path, data=None, follow_redirects=False):
        seen["request"] = (method, path, follow_redirects)
        return _Response()

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = OpenSubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Movie.Name.2024", download_id="123", language="en")
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["download_request"] == ("/api/v1/download", {"file_id": 123})
    assert seen["request"] == ("GET", "https://example.com/download/abc.srt", True)


def test_opensubtitles_download_raises_when_the_link_fails(monkeypatch):
    def _post_json(self, path, json):
        if path == "/api/v1/login":
            return _login_post_json(self, path, json)
        return {"link": "https://x/y.srt"}

    class _Response:
        is_success = False
        status_code = 404
        text = ""

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(
        ProviderHttpClient,
        "request",
        lambda self, method, path, data=None, follow_redirects=False: _Response(),
    )

    provider = OpenSubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Movie.Name.2024", download_id="123", language="en")
        )


def test_opensubtitles_reuses_the_same_client_across_calls(monkeypatch):
    login_calls = []

    def _post_json(self, path, json):
        login_calls.append(path)
        return {"token": "token123", "base_url": "api.opensubtitles.com"}

    monkeypatch.setattr(ProviderHttpClient, "post_json", _post_json)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})

    provider = OpenSubtitlesProvider(_config())
    provider.search("Movie Name", "en")
    provider.search("Movie Name", "en")

    assert len(login_calls) == 1


def test_opensubtitles_close_closes_the_client(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "post_json", _login_post_json)
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})
    closed = {"called": False}

    def _close(self):
        closed["called"] = True

    monkeypatch.setattr(ProviderHttpClient, "close", _close)

    provider = OpenSubtitlesProvider(_config())
    assert closed["called"] is False

    provider.search("Movie Name", "en")
    provider.close()

    assert closed["called"] is True
