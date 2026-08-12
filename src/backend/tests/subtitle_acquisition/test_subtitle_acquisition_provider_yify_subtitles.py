import io
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.yify_subtitles import YifySubtitlesProvider

_SEARCH_PAGE = """
<table class="other-subs">
<tbody>
<tr>
<td>10</td>
<td>English</td>
<td><a href="/subtitles/movie-name-english-yify-12345">subtitle Movie.Name.2024.WEB-DL</a></td>
<td></td>
<td>uploader1</td>
</tr>
<tr>
<td>5</td>
<td>Portuguese</td>
<td><a href="/subtitles/movie-name-portuguese-yify-67890">subtitle Movie.Name.2024.WEB-DL</a></td>
<td></td>
<td>uploader2</td>
</tr>
</tbody>
</table>
"""

_SUBTITLE_PAGE = '<a class="download-subtitle" href="/subtitle/12345.zip">Download</a>'


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "yify_subtitles", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_yify_subtitles_search_returns_empty_list_for_a_series(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for a series search")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = YifySubtitlesProvider(_config())

    assert provider.search("Some Show", "en", imdb_id=None) == []


def test_yify_subtitles_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = YifySubtitlesProvider(_config())

    assert provider.search("Movie Name", "xx", imdb_id="tt1234567") == []


def test_yify_subtitles_search_returns_empty_list_when_movie_not_found(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())

    assert provider.search("Movie Name", "en", imdb_id="tt0000000") == []


def test_yify_subtitles_search_returns_matching_language_subtitle(monkeypatch):
    seen = {}

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        seen["path"] = path
        return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    assert seen["path"] == "/movie-imdb/tt1234567"
    assert len(results) == 1
    assert results[0].release_name == "Movie.Name.2024.WEB-DL"
    assert results[0].download_id == "subtitles/movie-name-english-yify-12345"
    assert results[0].language == "English"
    assert (
        results[0].page_link == "https://yifysubtitles.ch/subtitles/movie-name-english-yify-12345"
    )


def test_yify_subtitles_download_extracts_srt_from_zip_archive(monkeypatch):
    seen = {}
    archive = _zip_bytes("Movie.Name.2024.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        seen.setdefault("paths", []).append(path)
        seen.setdefault("headers", []).append(headers)
        if path == "/subtitles/movie-name-english-yify-12345":
            return httpx.Response(200, text=_SUBTITLE_PAGE, request=httpx.Request("GET", path))
        if path == "/subtitle/12345.zip":
            return httpx.Response(200, content=archive, request=httpx.Request("GET", path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Movie.Name.2024",
            download_id="subtitles/movie-name-english-yify-12345",
            language="English",
            page_link="https://yifysubtitles.ch/subtitles/movie-name-english-yify-12345",
        )
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["paths"] == ["/subtitles/movie-name-english-yify-12345", "/subtitle/12345.zip"]
    assert all(
        headers == {"Referer": "https://yifysubtitles.ch/subtitles/movie-name-english-yify-12345"}
        for headers in seen["headers"]
    )


def test_yify_subtitles_download_raises_when_the_page_fetch_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="subtitles/x", language="English"
            )
        )


def test_yify_subtitles_download_raises_when_no_download_link_found(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200, text="<p>no download here</p>", request=httpx.Request("GET", path)
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="subtitles/x", language="English"
            )
        )


def test_yify_subtitles_download_raises_when_the_archive_is_not_a_zip(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/subtitles/x":
            return httpx.Response(200, text=_SUBTITLE_PAGE, request=httpx.Request("GET", path))
        return httpx.Response(200, content=b"not a zip", request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = YifySubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="subtitles/x", language="English"
            )
        )
