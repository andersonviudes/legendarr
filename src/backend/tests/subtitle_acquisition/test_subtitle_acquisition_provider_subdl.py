import io
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.subdl import SubdlProvider

_SEARCH_RESPONSE = {
    "status": True,
    "subtitles": [
        {
            "release_name": "ignored, releases wins instead",
            "releases": ["Movie.Name.2024.WEB-DL", "Movie.Name.2024.BluRay"],
            "name": "movie-name-english",
            "url": "/subtitle/12345.zip",
            "language": "EN",
            "subtitlePage": "/subtitles/movie-name-english",
            "author": "uploader1",
        },
        {
            "releases": [],
            "name": "no-url-entry",
            "language": "EN",
        },
    ],
}


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "subdl", "enabled": True, "api_key": "a-key"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_subdl_search_returns_empty_list_for_a_series(monkeypatch):
    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made for a series search")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SubdlProvider(_config())

    assert provider.search("Some Show", "en", imdb_id=None) == []


def test_subdl_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SubdlProvider(_config())

    assert provider.search("Movie Name", "xx", imdb_id="tt1234567") == []


def test_subdl_search_returns_empty_list_when_the_api_reports_no_results(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", lambda self, path: {"status": False, "error": "nope"}
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())

    assert provider.search("Movie Name", "en", imdb_id="tt0000000") == []


def test_subdl_search_sends_the_expected_query_and_parses_results(monkeypatch):
    seen = {}

    def _get_json(self, path):
        seen["path"] = path
        return _SEARCH_RESPONSE

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    query = parse_qs(urlsplit(seen["path"]).query)
    assert query["api_key"] == ["a-key"]
    assert query["imdb_id"] == ["tt1234567"]
    assert query["languages"] == ["EN"]
    assert query["type"] == ["movie"]
    assert query["releases"] == ["1"]
    assert query["bazarr"] == ["1"]

    assert len(results) == 1
    assert results[0] == SubtitleSearchResult(
        release_name="Movie.Name.2024.WEB-DL, Movie.Name.2024.BluRay",
        download_id="/subtitle/12345.zip",
        language="EN",
        page_link="https://subdl.com/subtitles/movie-name-english",
    )


def test_subdl_download_extracts_srt_from_zip_archive(monkeypatch):
    seen = {}
    archive = _zip_bytes("Movie.Name.2024.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        seen["path"] = path
        return httpx.Response(200, content=archive, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Movie.Name.2024",
            download_id="/subtitle/12345.zip",
            language="EN",
        )
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["path"] == "https://dl.subdl.com/subtitle/12345.zip"


def test_subdl_download_raises_when_the_download_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="/subtitle/x.zip", language="EN"
            )
        )


def test_subdl_download_raises_when_the_archive_is_not_a_zip(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"not a zip", request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="/subtitle/x.zip", language="EN"
            )
        )


def test_subdl_download_raises_when_the_archive_has_no_subtitle_file(monkeypatch):
    archive = _zip_bytes("readme.txt", "not a subtitle")

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=archive, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubdlProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="/subtitle/x.zip", language="EN"
            )
        )
