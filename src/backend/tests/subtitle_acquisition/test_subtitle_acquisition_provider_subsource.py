import io
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.subsource import SubsourceProvider

_MOVIE_SEARCH_RESPONSE = {
    "data": [
        {"title": "Movie Name", "alternateTitle": None, "releaseYear": 2024, "movieId": 555},
    ]
}

_SHOW_SEARCH_RESPONSE = {
    "data": [
        {"title": "Some Show", "alternateTitle": None, "releaseYear": 2020, "movieId": 555},
    ]
}

_EMPTY_SEARCH_RESPONSE = {"data": []}

_SUBTITLES_RESPONSE = {
    "success": True,
    "data": [
        {
            "subtitleId": 999,
            "releaseInfo": ["Movie.Name.2024.WEB-DL", "Movie.Name.2024.BluRay"],
            "language": "english",
            "link": "/subtitles/movie-name-english",
        },
        {"releaseInfo": [], "language": "english"},
    ],
}


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "subsource", "enabled": True, "api_key": "a-key"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def _dispatch_get_json(seen, movies_responses, subtitles_response):
    """Sequential `/movies/search` responses (one per call, for the imdb-then-text
    fallback), then a fixed `/subtitles` response for whichever call comes after."""
    movies_iter = iter(movies_responses)

    def _get_json(self, path):
        seen.setdefault("paths", []).append(path)
        if path.startswith("/movies/search"):
            return next(movies_iter)
        assert path.startswith("/subtitles?")
        return subtitles_response

    return _get_json


def test_subsource_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made for an unmapped language")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SubsourceProvider(_config())

    assert provider.search("Movie Name", "xx", imdb_id="tt1234567") == []


def test_subsource_search_returns_empty_list_with_no_imdb_id_or_episode(monkeypatch):
    def _get_json(self, path):
        raise AssertionError("no HTTP call should be made with nothing to search on")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = SubsourceProvider(_config())

    assert provider.search("Some Show", "en") == []


def test_subsource_search_returns_matching_movie_subtitle(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        _dispatch_get_json(seen, [_MOVIE_SEARCH_RESPONSE], _SUBTITLES_RESPONSE),
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    movies_query = parse_qs(urlsplit(seen["paths"][0]).query)
    assert movies_query["api_key"] == ["a-key"]
    assert movies_query["searchType"] == ["imdb"]
    assert movies_query["imdb"] == ["tt1234567"]
    assert "season" not in movies_query

    subtitles_query = parse_qs(urlsplit(seen["paths"][1]).query)
    assert subtitles_query["movieId"] == ["555"]
    assert subtitles_query["language"] == ["english"]
    assert subtitles_query["limit"] == ["100"]
    assert "seasonNumber" not in subtitles_query

    assert results == [
        SubtitleSearchResult(
            release_name="Movie.Name.2024.WEB-DL, Movie.Name.2024.BluRay",
            download_id="999",
            language="en",
            page_link="https://subsource.net/subtitles/movie-name-english",
        )
    ]


def test_subsource_search_returns_matching_tv_subtitle(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        _dispatch_get_json(seen, [_SHOW_SEARCH_RESPONSE], _SUBTITLES_RESPONSE),
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())
    results = provider.search("Some Show", "en", season=2, episode=5)

    movies_query = parse_qs(urlsplit(seen["paths"][0]).query)
    assert movies_query["searchType"] == ["text"]
    assert movies_query["q"] == ["some show"]
    assert movies_query["season"] == ["2"]

    subtitles_query = parse_qs(urlsplit(seen["paths"][1]).query)
    assert subtitles_query["movieId"] == ["555"]
    assert subtitles_query["seasonNumber"] == ["2"]
    assert subtitles_query["episodeNumber"] == ["5"]

    assert len(results) == 1


def test_subsource_search_falls_back_to_text_search_when_imdb_search_returns_no_results(
    monkeypatch,
):
    seen: dict = {}
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        _dispatch_get_json(
            seen, [_EMPTY_SEARCH_RESPONSE, _MOVIE_SEARCH_RESPONSE], _SUBTITLES_RESPONSE
        ),
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())
    results = provider.search("Movie Name", "en", imdb_id="tt1234567")

    assert len(seen["paths"]) == 3
    assert parse_qs(urlsplit(seen["paths"][0]).query)["searchType"] == ["imdb"]
    assert parse_qs(urlsplit(seen["paths"][1]).query)["searchType"] == ["text"]
    assert len(results) == 1


def test_subsource_search_returns_empty_list_when_no_title_matches(monkeypatch):
    def _get_json(self, path):
        assert path.startswith("/movies/search")
        return {"data": [{"title": "A Totally Different Movie", "movieId": 1}]}

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())

    assert provider.search("Movie Name", "en", imdb_id="tt1234567") == []


def test_subsource_search_returns_empty_list_when_the_api_reports_no_success(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        _dispatch_get_json({}, [_MOVIE_SEARCH_RESPONSE], {"success": False, "data": []}),
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())

    assert provider.search("Movie Name", "en", imdb_id="tt1234567") == []


def test_subsource_download_extracts_srt_from_zip_archive(monkeypatch):
    seen = {}
    archive = _zip_bytes("Movie.Name.2024.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        seen["path"] = path
        return httpx.Response(200, content=archive, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Movie Name 2024", download_id="999", language="en")
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    assert seen["path"] == "/subtitles/999/download?api_key=a-key"


def test_subsource_download_raises_when_the_download_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Movie Name 2024", download_id="999", language="en")
        )


def test_subsource_download_raises_when_the_archive_is_not_a_zip(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"not a zip", request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Movie Name 2024", download_id="999", language="en")
        )


def test_subsource_download_raises_when_the_archive_has_no_subtitle_file(monkeypatch):
    archive = _zip_bytes("readme.txt", "not a subtitle")

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=archive, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = SubsourceProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Movie Name 2024", download_id="999", language="en")
        )
