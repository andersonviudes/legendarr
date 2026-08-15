import io
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.betaseries import BetaSeriesProvider

_EPISODES_RESPONSE = {
    "errors": [],
    "episodes": [
        {
            "subtitles": [
                {
                    "id": 1,
                    "language": "vo",
                    "file": "Foo.Show.S01E02.en.srt",
                    "url": "https://sub.betaseries.com/subtitle/1.srt",
                    "source": "addic7ed",
                },
                {
                    "id": 2,
                    "language": "vf",
                    "file": "Foo.Show.S01E02.fr.srt",
                    "url": "https://sub.betaseries.com/subtitle/2.srt",
                    "source": "addic7ed",
                },
                {
                    "id": 3,
                    "language": "vo",
                    "file": "Foo.Show.S01E02.dead.srt",
                    "url": "https://sub.betaseries.com/subtitle/3.srt",
                    "source": "seriessub",
                },
            ]
        }
    ],
}


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "betaseries", "enabled": True, "api_key": "a-token"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _zip_bytes(filename: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


def test_betaseries_search_returns_empty_list_with_no_tvdb_id_season_or_episode(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made with nothing to search on")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())

    assert provider.search("Foo Show", "en") == []
    assert provider.search("Foo Show", "en", tvdb_id=123, season=1) == []


def test_betaseries_search_returns_empty_list_for_unsupported_language(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unsupported language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())

    assert provider.search("Foo Show", "de", tvdb_id=123, season=1, episode=2) == []


def test_betaseries_search_returns_matching_subtitle_and_filters_dead_source(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        query = parse_qs(urlsplit(path).query)
        assert query["key"] == ["a-token"]
        assert query["thetvdb_id"] == ["123"]
        assert query["season"] == ["1"]
        assert query["episode"] == ["2"]
        return httpx.Response(200, json=_EPISODES_RESPONSE, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())
    results = provider.search("Foo Show", "en", tvdb_id=123, season=1, episode=2)

    assert results == [
        SubtitleSearchResult(
            release_name="Foo.Show.S01E02.en.srt",
            download_id="https://sub.betaseries.com/subtitle/1.srt",
            language="en",
        )
    ]


def test_betaseries_search_returns_empty_list_when_no_episode_found(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            400,
            json={"errors": [{"code": 4001, "message": "no episode"}]},
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())

    assert provider.search("Foo Show", "en", tvdb_id=123, season=1, episode=2) == []


def test_betaseries_search_raises_when_token_is_rejected(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(
            400,
            json={"errors": [{"code": 1001, "message": "invalid token"}]},
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.search("Foo Show", "en", tvdb_id=123, season=1, episode=2)


def test_betaseries_download_returns_subtitle_text(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        assert path == "https://sub.betaseries.com/subtitle/1.srt"
        return httpx.Response(
            200,
            content=_zip_bytes("Foo.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"),
            request=httpx.Request(method, path),
        )

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Foo",
            download_id="https://sub.betaseries.com/subtitle/1.srt",
            language="en",
        )
    )

    assert "Hi" in result


def test_betaseries_download_raises_on_404(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = BetaSeriesProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Foo",
                download_id="https://sub.betaseries.com/subtitle/1.srt",
                language="en",
            )
        )
