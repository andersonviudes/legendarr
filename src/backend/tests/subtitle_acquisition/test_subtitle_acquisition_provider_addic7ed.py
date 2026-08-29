import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.addic7ed import Addic7edProvider
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

_SEARCH_PAGE = """
<table class="tabel">
<tr><td><a href="movie/12345">Movie Name (2024)</a></td></tr>
<tr><td><a href="movie/67890">Some Other Movie (2019)</a></td></tr>
</table>
"""

_MOVIE_PAGE = (
    '<table align="center" border="0" class="tabel95" width="100%">'
    "<td></td>"
    '<tr><td class="NewsTitle">Movie Name</td><td>Version WEB-DL.x264-GROUP, works fine</td></tr>'
    "<td></td><td></td>"
    "<tr><td></td><td></td><td></td><td></td>"
    "<td>English</td><td></td><td>Completed</td><td></td>"
    '<td><a href="/original/12345/0">download</a></td></tr>'
    "</table>"
)

# Same as `_MOVIE_PAGE`, plus a third row (table index 6) carrying the HI icon marker
# Bazarr's own `query_movie` reads at `row3.contents[1].contents[1]` — a filler `<td>`
# at index 5 keeps that row landing on index 6, same shape `_MOVIE_PAGE`'s own filler
# `<td>`s already use to position its two real rows at indices 1 and 4.
_MOVIE_PAGE_WITH_HI = (
    '<table align="center" border="0" class="tabel95" width="100%">'
    "<td></td>"
    '<tr><td class="NewsTitle">Movie Name</td><td>Version WEB-DL.x264-GROUP, works fine</td></tr>'
    "<td></td><td></td>"
    "<tr><td></td><td></td><td></td><td></td>"
    "<td>English</td><td></td><td>Completed</td><td></td>"
    '<td><a href="/original/12345/0">download</a></td></tr>'
    "<td></td>"
    '<tr><td></td><td><span></span><img src="https://x/hi.jpg"></td></tr>'
    "</table>"
)


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "addic7ed", "enabled": True, "username": "user", "password": "pass"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _successful_login_request(method, path, data=None, headers=None, follow_redirects=False):
    if path == "/login.php":
        return httpx.Response(200, request=httpx.Request("GET", "https://x/login.php"))
    if path == "/dologin.php":
        return httpx.Response(302, request=httpx.Request("POST", "https://x/dologin.php"))
    raise AssertionError(f"unexpected request to {path}")


def test_addic7ed_search_returns_empty_list_for_a_series(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for a series search")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())

    assert provider.search("Some Show", "en", imdb_id=None) == []


def test_addic7ed_search_raises_when_login_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/login.php":
            return httpx.Response(200, request=httpx.Request("GET", "https://x/login.php"))
        return httpx.Response(
            200, text="Wrong password", request=httpx.Request("POST", "https://x/dologin.php")
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.search("Movie Name", "en", imdb_id="tt1234567")


def test_addic7ed_search_returns_matching_movie_subtitle(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        if path.startswith("/search.php"):
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request("GET", path))
        if path == "/movie/12345":
            return httpx.Response(200, text=_MOVIE_PAGE, request=httpx.Request("GET", path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    assert len(results) == 1
    assert results[0].release_name == "WEB-DL.x264-GROUP"
    assert results[0].download_id == "original/12345/0"
    assert results[0].language == "English"
    assert results[0].page_link == "https://www.addic7ed.com/movie/12345"
    # `_MOVIE_PAGE` has no third row to read the HI icon from — unknown, not "not HI".
    assert results[0].hearing_impaired is None


def test_addic7ed_search_reads_the_hi_icon_marker(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        if path.startswith("/search.php"):
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request("GET", path))
        if path == "/movie/12345":
            return httpx.Response(200, text=_MOVIE_PAGE_WITH_HI, request=httpx.Request("GET", path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    assert results[0].hearing_impaired is True


def test_addic7ed_search_returns_empty_list_when_no_movie_matches(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        if path.startswith("/search.php"):
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request("GET", path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())

    assert provider.search("Nonexistent Movie", "en", imdb_id="tt0000000") == []


def test_addic7ed_download_sends_referer_and_returns_text(monkeypatch):
    seen = {}

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        seen["path"] = path
        seen["headers"] = headers
        return httpx.Response(
            200,
            text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
            request=httpx.Request("GET", path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Movie.Name.2024",
            download_id="original/12345/0",
            language="en",
            page_link="https://www.addic7ed.com/movie/12345",
        )
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["path"] == "/original/12345/0"
    assert seen["headers"] == {"Referer": "https://www.addic7ed.com/movie/12345"}


def test_addic7ed_download_raises_when_it_fails(monkeypatch):
    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        return httpx.Response(404, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Movie.Name.2024", download_id="original/12345/0", language="en"
            )
        )


def test_addic7ed_reuses_the_same_client_and_session_across_calls(monkeypatch):
    login_calls = []

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path == "/login.php":
            login_calls.append(path)
            return httpx.Response(200, request=httpx.Request("GET", path))
        if path == "/dologin.php":
            return httpx.Response(302, request=httpx.Request("POST", path))
        if path.startswith("/search.php"):
            return httpx.Response(200, text=_SEARCH_PAGE, request=httpx.Request("GET", path))
        if path == "/movie/12345":
            return httpx.Response(200, text=_MOVIE_PAGE, request=httpx.Request("GET", path))
        raise AssertionError(f"unexpected request to {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = Addic7edProvider(_config())
    provider.search("Movie Name", "en", imdb_id="tt1234567")
    provider.search("Movie Name", "en", imdb_id="tt1234567")

    assert len(login_calls) == 1


def test_addic7ed_close_closes_the_client(monkeypatch):
    closed = {"called": False}

    def _request(self, method, path, data=None, headers=None, follow_redirects=False):
        if path in ("/login.php", "/dologin.php"):
            return _successful_login_request(method, path, data, headers, follow_redirects)
        return httpx.Response(200, text="content", request=httpx.Request(method, path))

    def _close(self):
        closed["called"] = True

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", _close)

    provider = Addic7edProvider(_config())
    provider.search("Some Show", "en", imdb_id=None)  # no client created yet
    assert closed["called"] is False

    provider.download(
        SubtitleSearchResult(release_name="x", download_id="original/1/0", language="en")
    )
    provider.close()

    assert closed["called"] is True
