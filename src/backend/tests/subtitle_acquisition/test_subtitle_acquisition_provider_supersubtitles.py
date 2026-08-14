import io
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.supersubtitles import (
    SupersubtitlesProvider,
)

_MOVIE_SEARCH_PAGE = """
<table>
<tr><td>header</td></tr>
<tr>
<td>
<div class="eredeti">Foo Movie (2010) (WEB-DL.720p-GROUP)</div>
<small>Angol</small>
<a href="/index.php?action=letolt&amp;fnev=Foo.Movie.WEB-DL.srt&amp;felirat=555">Download</a>
</td>
</tr>
<tr>
<td>
<div class="eredeti">Foo Movie (2010) (HDTV-GROUP)</div>
<small>Magyar</small>
<a href="/index.php?action=letolt&amp;fnev=Foo.Movie.HDTV.srt&amp;felirat=556">Download</a>
</td>
</tr>
</table>
"""

_AUTONAME_RESPONSE = [
    {"name": "Foo Show (2016)", "ID": "123"},
    {"name": "Other Show (2011)", "ID": "456"},
]

_XBMC_RESPONSE = {
    "10": {
        "language": "Angol",
        "nev": "Foo Show - 1x02 (WEB-DL.720p-GROUP)",
        "felirat": "777",
        "evad": "1",
        "ep": "2",
        "feltolto": "uploader1",
        "evadpakk": "0",
    },
    "11": {
        "language": "Magyar",
        "nev": "Foo Show - 1x02 (HDTV-GROUP)",
        "felirat": "778",
        "evad": "1",
        "ep": "2",
        "feltolto": "uploader2",
        "evadpakk": "0",
    },
}


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "supersubtitles", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def _dispatch_get_json(autoname_response, xbmc_response, seen=None):
    def _get_json(self, path):
        if seen is not None:
            seen.setdefault("paths", []).append(path)
        if "action=autoname" in path:
            return autoname_response
        assert "action=xbmc" in path
        return xbmc_response

    return _get_json


def test_supersubtitles_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SupersubtitlesProvider(_config())

    assert provider.search("Foo Movie", "xx", imdb_id="tt1234567") == []


def test_supersubtitles_search_returns_empty_list_with_no_imdb_id_or_episode(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made with nothing to search on")

    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made with nothing to search on")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SupersubtitlesProvider(_config())

    assert provider.search("Foo Show", "en") == []


def test_supersubtitles_search_returns_matching_movie_subtitle(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        assert method == "GET"
        query = parse_qs(urlsplit(path).query)
        assert query["search"] == ["Foo Movie"]
        assert query["tab"] == ["film"]
        return httpx.Response(200, text=_MOVIE_SEARCH_PAGE, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = SupersubtitlesProvider(_config())
    results = provider.search("Foo Movie", "en", imdb_id="tt1234567")

    assert results == [
        SubtitleSearchResult(
            release_name="Foo Movie (2010) (WEB-DL.720p-GROUP)",
            download_id="555",
            language="en",
            page_link="https://www.feliratok.eu/index.php?action=letolt&felirat=555",
        )
    ]


def test_supersubtitles_search_returns_empty_list_when_movie_page_request_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = SupersubtitlesProvider(_config())

    assert provider.search("Foo Movie", "en", imdb_id="tt1234567") == []


def test_supersubtitles_search_returns_matching_tv_subtitle(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        _dispatch_get_json(_AUTONAME_RESPONSE, _XBMC_RESPONSE, seen),
    )

    provider = SupersubtitlesProvider(_config())
    results = provider.search("Foo Show", "en", season=1, episode=2)

    autoname_query = parse_qs(urlsplit(seen["paths"][0]).query)
    assert autoname_query["term"] == ["Foo Show"]
    assert autoname_query["action"] == ["autoname"]
    assert seen["paths"][1] == "/index.php?action=xbmc&sid=123&ev=1&rtol=2"

    assert results == [
        SubtitleSearchResult(
            release_name="Foo Show - 1x02 (WEB-DL.720p-GROUP)",
            download_id="777",
            language="en",
            page_link="https://www.feliratok.eu/index.php?action=letolt&felirat=777",
        )
    ]


def test_supersubtitles_search_returns_empty_list_when_series_not_found(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "get_json", _dispatch_get_json(_AUTONAME_RESPONSE, _XBMC_RESPONSE)
    )

    provider = SupersubtitlesProvider(_config())

    assert provider.search("Nonexistent Show", "en", season=1, episode=2) == []


def test_supersubtitles_download_returns_subtitle_text(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        assert path == "/index.php?action=letolt&felirat=777"
        return httpx.Response(
            200,
            content=_zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"),
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = SupersubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Foo", download_id="777", language="en")
    )

    assert "Hi" in result


def test_supersubtitles_download_falls_back_to_raw_text_when_not_zipped(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200,
            content=b"1\n00:00:00,000 --> 00:00:01,000\nHi\n\n",
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = SupersubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Foo", download_id="777", language="en")
    )

    assert "Hi" in result


def test_supersubtitles_download_raises_when_it_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = SupersubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Foo", download_id="777", language="en")
        )
