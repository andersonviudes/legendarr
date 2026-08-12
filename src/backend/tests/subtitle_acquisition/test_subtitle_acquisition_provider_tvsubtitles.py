import io
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.tvsubtitles import TVsubtitlesProvider

_SEARCH_PAGE = """
<div class="left">
<ul>
<li><div><a href="/tvshow-123.html">Foo Show (2010-2015)</a></div></li>
<li><div><a href="/tvshow-456.html">Other Show (2011-2016)</a></div></li>
</ul>
</div>
"""

_SEASON_PAGE = """
<table id="table5">
<tr><td>1x01</td><td><a href="episode-100.html">1x01</a></td></tr>
<tr><td>1x02</td><td><a href="episode-200.html">1x02</a></td></tr>
</table>
"""

_EPISODE_PAGE = """
<a href="/subtitle-789.html">
<div class="subtitlen">
<h5><img src="images/flags/en.gif">Foo.Show.S01E02.HDTV.x264-GROUP</h5>
<p title="rip">HDTV</p>
</div>
</a>
<a href="/subtitle-790.html">
<div class="subtitlen">
<h5><img src="images/flags/fr.gif">Foo.Show.S01E02.FRENCH.HDTV.x264-GROUP</h5>
<p title="rip">HDTV</p>
</div>
</a>
"""

_DOWNLOAD_PAGE = "<script>s0='download/789';\ns1='.zip';\n</script>"


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "tvsubtitles", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_tvsubtitles_search_returns_empty_list_when_season_or_episode_is_missing(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made without season/episode")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    assert provider.search("Foo Show", "en", season=1, episode=None) == []
    assert provider.search("Foo Show", "en", season=None, episode=2) == []


def test_tvsubtitles_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    assert provider.search("Foo Show", "xx", season=1, episode=2) == []


def test_tvsubtitles_search_returns_matching_episode_subtitle(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/search1.php":
            assert data == {"qs": "Foo Show"}
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request(method, path))
        if path == "/tvshow-123-1.html":
            return httpx.Response(200, text=_SEASON_PAGE, request=httpx.Request(method, path))
        if path == "/episode-200.html":
            return httpx.Response(200, text=_EPISODE_PAGE, request=httpx.Request(method, path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())
    results = provider.search("Foo Show", "en", season=1, episode=2)

    assert len(results) == 1
    assert results[0].download_id == "789"
    assert results[0].language == "en"
    assert results[0].release_name == "HDTV, Foo.Show.S01E02.HDTV.x264-GROUP"
    assert results[0].page_link == "http://www.tvsubtitles.net/subtitle-789.html"


def test_tvsubtitles_search_returns_empty_list_when_show_not_found(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/search1.php":
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request(method, path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    assert provider.search("Nonexistent Show", "en", season=1, episode=2) == []


def test_tvsubtitles_search_returns_empty_list_when_episode_not_found(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/search1.php":
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request(method, path))
        if path == "/tvshow-123-1.html":
            return httpx.Response(200, text=_SEASON_PAGE, request=httpx.Request(method, path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    assert provider.search("Foo Show", "en", season=1, episode=9) == []


def test_tvsubtitles_download_returns_subtitle_text(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/download-789.html":
            return httpx.Response(200, text=_DOWNLOAD_PAGE, request=httpx.Request(method, path))
        if path == "/download/789.zip":
            return httpx.Response(
                200,
                content=_zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"),
                request=httpx.Request(method, path),
            )
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Foo", download_id="789", language="en")
    )

    assert "Hi" in result


def test_tvsubtitles_download_raises_when_no_download_link_found(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(200, text="<script></script>", request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Foo", download_id="789", language="en")
        )


def test_tvsubtitles_download_raises_when_it_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = TVsubtitlesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Foo", download_id="789", language="en")
        )
