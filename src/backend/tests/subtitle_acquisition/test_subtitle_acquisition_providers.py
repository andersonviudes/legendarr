import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import OpenSubtitlesProvider


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "opensubtitles", "enabled": True, "api_key": "a-key"}
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


def test_opensubtitles_search_returns_one_result_per_file(monkeypatch):
    seen = {}

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

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

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(
        _config(include_ai_translated=True, include_machine_translated=True)
    )
    provider.search("Movie Name", "en")

    assert "ai_translated=include" in seen["path"]
    assert "machine_translated=include" in seen["path"]


def test_opensubtitles_search_passes_imdb_id_and_moviehash_when_given(monkeypatch):
    seen = {}

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config())
    provider.search("Movie Name", "en", imdb_id="tt1234567", moviehash="abc123")

    assert "imdb_id=1234567" in seen["path"]
    assert "moviehash=abc123" in seen["path"]


def test_opensubtitles_search_ignores_moviehash_when_use_hash_is_disabled(monkeypatch):
    seen = {}

    def _get_json(self, path):
        seen["path"] = path
        return _search_response()

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config(use_hash=False))
    provider.search("Movie Name", "en", moviehash="abc123")

    assert "moviehash" not in seen["path"]


def test_opensubtitles_search_returns_empty_list_when_no_results(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "get_json", lambda self, path: {"data": []})
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config())

    assert provider.search("Movie Name", "en") == []


def test_opensubtitles_download_fetches_link_then_returns_its_text(monkeypatch):
    seen = {}

    def _post_json(self, path, json):
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
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Movie.Name.2024", download_id="123", language="en")
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["download_request"] == ("/api/v1/download", {"file_id": 123})
    assert seen["request"] == ("GET", "https://example.com/download/abc.srt", True)


def test_opensubtitles_download_raises_when_the_link_fails(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "post_json", lambda self, path, json: {"link": "https://x/y.srt"}
    )

    class _Response:
        is_success = False
        status_code = 404
        text = ""

    monkeypatch.setattr(
        ProviderHttpClient,
        "request",
        lambda self, method, path, data=None, follow_redirects=False: _Response(),
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = OpenSubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Movie.Name.2024", download_id="123", language="en")
        )
