import io
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.greeksubtitles import (
    GreekSubtitlesProvider,
)

_SEARCH_RESULTS_PAGE = """
<table>
<tr>
<td class="latest_name">
<a href="http://gr.greek-subtitles.com/tainies/12345/foo-movie.html">Foo Movie (2010)</a>
<img src="/images/flags/en.png">
</td>
</tr>
<tr>
<td class="latest_name">
<a href="http://gr.greek-subtitles.com/tainies/12346/foo-movie-el.html">Foo Movie GR (2010)</a>
<img src="/images/flags/el.png">
</td>
</tr>
</table>
"""


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "greeksubtitles", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_greeksubtitles_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unsupported language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())

    assert provider.search("Foo Movie", "xx") == []


def test_greeksubtitles_search_returns_matching_movie_subtitle(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        query = parse_qs(urlsplit(path).query)
        assert query["name"] == ["Foo Movie"]
        return httpx.Response(200, text=_SEARCH_RESULTS_PAGE, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())
    results = provider.search("Foo Movie", "en")

    assert results == [
        SubtitleSearchResult(
            release_name="Foo Movie (2010)",
            download_id="12345",
            language="en",
            page_link="http://gr.greek-subtitles.com/tainies/12345/foo-movie.html",
        )
    ]


def test_greeksubtitles_search_includes_season_and_episode_in_query(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        query = parse_qs(urlsplit(path).query)
        assert query["name"] == ["Foo Show S01E02"]
        return httpx.Response(200, text="", request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())

    assert provider.search("Foo Show", "en", season=1, episode=2) == []


def test_greeksubtitles_search_returns_empty_list_when_page_request_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())

    assert provider.search("Foo Movie", "en") == []


def test_greeksubtitles_download_returns_subtitle_text(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        assert path == "/getp.php?id=12345"
        assert headers == {"Referer": "http://example.com/page"}
        return httpx.Response(
            200,
            content=_zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"),
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo",
            download_id="12345",
            language="en",
            page_link="http://example.com/page",
        )
    )

    assert "Hi" in result


def test_greeksubtitles_download_falls_back_to_raw_text_when_not_zipped(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200,
            content=b"1\n00:00:00,000 --> 00:00:01,000\nHi\n\n",
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Foo", download_id="12345", language="en")
    )

    assert "Hi" in result


def test_greeksubtitles_download_raises_when_it_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = GreekSubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Foo", download_id="12345", language="en")
        )
