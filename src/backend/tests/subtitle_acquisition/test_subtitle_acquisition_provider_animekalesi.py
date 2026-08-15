import io
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.animekalesi import AnimeKalesiProvider
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

_SERIES_LIST_PAGE = """
<table>
<tr><td id="bolumler"><a href="/bolumler-foo-show.html">Foo Show</a></td></tr>
<tr><td id="bolumler"><a href="/bolumler-other-show.html">Other Show</a></td></tr>
</table>
"""

_EPISODE_LISTING_PAGE = """
<table>
<tr>
<td id="ayazi_indir">
<a href="indir_bolum-foo-show-1.html" title="1. Sezon 1. Bölüm Türkçe Altyazısı">Bölüm 1</a>
</td>
</tr>
<tr>
<td id="ayazi_indir">
<a href="indir_bolum-foo-show-2.html" title="1. Sezon 2. Bölüm Türkçe Altyazısı">Bölüm 2</a>
</td>
</tr>
</table>
"""

_EPISODE_PAGE = """
<div id="altyazi_indir"><a href="indir.php?id=777">İndir</a></div>
"""


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "animekalesi", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def _dispatch_search(series_page, listing_page, seen=None):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if seen is not None:
            seen.setdefault("paths", []).append(path)
        if path == "/tum-anime-serileri.html":
            return httpx.Response(200, text=series_page, request=httpx.Request(method, path))
        assert path == "/altyazib-foo-show.html"
        return httpx.Response(200, text=listing_page, request=httpx.Request(method, path))

    return _request


def test_animekalesi_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unsupported language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())

    assert provider.search("Foo Show", "en", season=1, episode=2) == []


def test_animekalesi_search_returns_empty_list_with_no_season_or_episode(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made with no season/episode resolved")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())

    assert provider.search("Foo Show", "tr") == []


def test_animekalesi_search_returns_empty_list_when_series_not_found(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "request", _dispatch_search(_SERIES_LIST_PAGE, _EPISODE_LISTING_PAGE)
    )

    provider = AnimeKalesiProvider(_config())

    assert provider.search("Nonexistent Show", "tr", season=1, episode=2) == []


def test_animekalesi_search_returns_empty_list_when_episode_not_found(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient, "request", _dispatch_search(_SERIES_LIST_PAGE, _EPISODE_LISTING_PAGE)
    )

    provider = AnimeKalesiProvider(_config())

    assert provider.search("Foo Show", "tr", season=1, episode=9) == []


def test_animekalesi_search_returns_matching_episode_subtitle(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        ProviderHttpClient,
        "request",
        _dispatch_search(_SERIES_LIST_PAGE, _EPISODE_LISTING_PAGE, seen),
    )

    provider = AnimeKalesiProvider(_config())
    results = provider.search("Foo Show", "tr", season=1, episode=2)

    assert seen["paths"] == ["/tum-anime-serileri.html", "/altyazib-foo-show.html"]
    assert results == [
        SubtitleSearchResult(
            release_name="Foo Show - S01E02",
            download_id="/indir_bolum-foo-show-2.html",
            language="tr",
            page_link="https://www.animekalesi.com/indir_bolum-foo-show-2.html",
        )
    ]


def test_animekalesi_download_returns_subtitle_text(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if path == "/indir_bolum-foo-show-2.html":
            return httpx.Response(200, text=_EPISODE_PAGE, request=httpx.Request(method, path))
        assert path == "/indir.php?id=777"
        return httpx.Response(
            200,
            content=_zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"),
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo", download_id="/indir_bolum-foo-show-2.html", language="tr"
        )
    )

    assert "Hi" in result


def test_animekalesi_download_falls_back_to_raw_text_when_not_zipped(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if path == "/indir_bolum-foo-show-2.html":
            return httpx.Response(200, text=_EPISODE_PAGE, request=httpx.Request(method, path))
        return httpx.Response(
            200,
            content=b"1\n00:00:00,000 --> 00:00:01,000\nHi\n\n",
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo", download_id="/indir_bolum-foo-show-2.html", language="tr"
        )
    )

    assert "Hi" in result


def test_animekalesi_download_raises_when_episode_page_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Foo", download_id="/indir_bolum-foo-show-2.html", language="tr"
            )
        )


def test_animekalesi_download_raises_when_no_download_link_found(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            200, text="<div>no link here</div>", request=httpx.Request(method, path)
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Foo", download_id="/indir_bolum-foo-show-2.html", language="tr"
            )
        )


def test_animekalesi_download_raises_when_file_request_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if path == "/indir_bolum-foo-show-2.html":
            return httpx.Response(200, text=_EPISODE_PAGE, request=httpx.Request(method, path))
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeKalesiProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Foo", download_id="/indir_bolum-foo-show-2.html", language="tr"
            )
        )
