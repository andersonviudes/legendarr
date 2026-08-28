import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.providers.napiprojekt import NapiprojektProvider
from legendarr_backend.subtitle_acquisition.providers.napiprojekt_hash import (
    compute_napiprojekt_hash,
    napiprojekt_subhash,
)

_SUBTITLE_TEXT = "1\n00:00:00,000 --> 00:00:01,000\nCześć\n\n"


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "napiprojekt", "enabled": True}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


def _write_video(tmp_path, content: bytes = b"video-bytes"):
    video_path = tmp_path / "Foo.mkv"
    video_path.write_bytes(content)
    return video_path


def test_napiprojekt_search_returns_empty_list_for_unsupported_language(monkeypatch, tmp_path):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for an unsupported language")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = NapiprojektProvider(_config())
    video_path = _write_video(tmp_path)

    assert provider.search("Foo", "en", video_path=video_path) == []


def test_napiprojekt_search_returns_empty_list_when_no_video_path(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made with no video to hash")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = NapiprojektProvider(_config())

    assert provider.search("Foo", "pl", video_path=None) == []


def test_napiprojekt_search_returns_empty_list_when_video_path_does_not_exist(
    monkeypatch, tmp_path
):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        raise AssertionError("no HTTP call should be made for a missing file")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = NapiprojektProvider(_config())

    assert provider.search("Foo", "pl", video_path=tmp_path / "missing.mkv") == []


def test_napiprojekt_search_returns_empty_list_when_not_found(monkeypatch, tmp_path):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"NPc0", request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = NapiprojektProvider(_config())
    video_path = _write_video(tmp_path)

    assert provider.search("Foo", "pl", video_path=video_path) == []


def test_napiprojekt_search_returns_a_hash_matched_result(monkeypatch, tmp_path):
    seen = {}
    video_path = _write_video(tmp_path)
    expected_hash = compute_napiprojekt_hash(video_path)
    expected_subhash = napiprojekt_subhash(expected_hash)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        seen["path"] = path
        return httpx.Response(200, text=_SUBTITLE_TEXT, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = NapiprojektProvider(_config())
    results = provider.search("Foo", "pl", video_path=video_path)

    assert seen["path"] == (
        "/unit_napisy/dl.php?v=dreambox&kolejka=false&nick=&pass=&napios=Linux"
        f"&l=PL&f={expected_hash}&t={expected_subhash}"
    )
    assert results == [
        SubtitleSearchResult(release_name="Foo.mkv", download_id=expected_hash, language="pl")
    ]


def test_napiprojekt_download_reissues_the_same_request_and_returns_the_content(monkeypatch):
    seen = {}

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        seen["path"] = path
        return httpx.Response(200, text=_SUBTITLE_TEXT, request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = NapiprojektProvider(_config())
    result = provider.download(
        SubtitleSearchResult(release_name="Foo.mkv", download_id="a" * 32, language="pl")
    )

    expected_subhash = napiprojekt_subhash("a" * 32)
    assert seen["path"] == (
        "/unit_napisy/dl.php?v=dreambox&kolejka=false&nick=&pass=&napios=Linux"
        f"&l=PL&f={'a' * 32}&t={expected_subhash}"
    )
    assert result == _SUBTITLE_TEXT


def test_napiprojekt_download_raises_when_not_found(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"NPc0", request=httpx.Request("GET", path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

    provider = NapiprojektProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(release_name="Foo.mkv", download_id="a" * 32, language="pl")
        )
