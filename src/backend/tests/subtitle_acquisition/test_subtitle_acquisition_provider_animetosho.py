import lzma
from datetime import date

import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers import animetosho
from legendarr_backend.subtitle_acquisition.providers.animetosho import AnimeToshoProvider
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


def _config(**overrides) -> SubtitleProviderConfig:
    data = {"kind": "animetosho", "enabled": True, "api_key": "anidb-key"}
    data.update(overrides)
    return SubtitleProviderConfig(**data)


@pytest.fixture(autouse=True)
def _reset_animetosho_caches(monkeypatch):
    """These caches/the quota counter are module-level, process-lifetime state (see
    `providers/animetosho.py`'s module docstring) — reset between tests so one test's
    cached mapping/quota doesn't leak into the next."""
    monkeypatch.setattr(animetosho, "_mapping_cache_root", None)
    monkeypatch.setattr(animetosho, "_mapping_cache_fetched_at", 0.0)
    monkeypatch.setattr(animetosho, "_episodes_cache", {})
    monkeypatch.setattr(animetosho, "_daily_quota_date", None)
    monkeypatch.setattr(animetosho, "_daily_quota_count", 0)


_MAPPING_XML = b"""<anime-list>
  <anime anidbid="17495" tvdbid="389597" defaulttvdbseason="1" episodeoffset="0" />
</anime-list>"""

_ANIDB_EPISODES_XML = b"""<anime>
  <episodes>
    <episode id="277518"><epno>12</epno></episode>
  </episodes>
</anime>"""


def _mapping_and_anidb_response(
    self, method, path, data=None, json=None, headers=None, follow_redirects=False
):
    if "raw.githubusercontent.com" in path:
        return httpx.Response(200, content=_MAPPING_XML, request=httpx.Request(method, path))
    if "api.anidb.net" in path:
        return httpx.Response(200, content=_ANIDB_EPISODES_XML, request=httpx.Request(method, path))
    raise AssertionError(f"unexpected request: {path}")


def test_animetosho_search_returns_empty_list_without_tvdb_id_season_or_episode():
    provider = AnimeToshoProvider(_config())

    assert provider.search("Solo Leveling", "en", season=1, episode=12) == []
    assert provider.search("Solo Leveling", "en", tvdb_id=389597, episode=12) == []
    assert provider.search("Solo Leveling", "en", tvdb_id=389597, season=1) == []


def test_animetosho_search_returns_empty_list_for_unsupported_language():
    provider = AnimeToshoProvider(_config())

    assert provider.search("Solo Leveling", "xx", season=1, episode=12, tvdb_id=389597) == []


def test_animetosho_search_without_api_key_falls_back_to_anime_id_search(monkeypatch):
    """No AniDB API client key configured: `search()` skips `_resolve_anidb_episode_id`
    (and the AniDB HTTP API entirely — asserted below by only stubbing the mapping-list
    host) and matches episodes off each file's own name instead
    (`_search_by_anime_id`)."""

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if "raw.githubusercontent.com" in path:
            return httpx.Response(200, content=_MAPPING_XML, request=httpx.Request(method, path))
        raise AssertionError(f"AniDB API should not be called without an api_key: {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    def _get_json(self, path):
        if path == "/json?aid=17495&limit=200":
            return [
                {
                    "id": 608526,
                    "title": "[EMBER] Solo Leveling - 12",
                    "timestamp": 1,
                    "status": "complete",
                }
            ]
        if path == "/json?show=torrent&id=608526":
            return {
                "title": "[EMBER] Solo Leveling - 12",
                "files": [
                    {
                        "filename": "[EMBER] Solo Leveling - 12 [1080p].mkv",
                        "attachments": [
                            {"id": 1961547, "type": "subtitle", "info": {"lang": "eng"}},
                            {"id": 1, "type": "other", "info": {}},
                        ],
                    }
                ],
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = AnimeToshoProvider(_config(api_key=None))
    results = provider.search("Solo Leveling", "en", season=1, episode=12, tvdb_id=389597)

    assert results == [
        SubtitleSearchResult(
            release_name="[EMBER] Solo Leveling - 12", download_id="1961547", language="en"
        )
    ]


def test_animetosho_search_without_api_key_only_matches_the_target_episode_file(monkeypatch):
    """A season-batch release only contributes the one file that's actually the
    requested episode — every other file in the same entry is skipped."""

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if "raw.githubusercontent.com" in path:
            return httpx.Response(200, content=_MAPPING_XML, request=httpx.Request(method, path))
        raise AssertionError(f"AniDB API should not be called without an api_key: {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    def _get_json(self, path):
        if path == "/json?aid=17495&limit=200":
            return [
                {
                    "id": 900,
                    "title": "[Group] Solo Leveling Batch",
                    "timestamp": 1,
                    "status": "complete",
                }
            ]
        if path == "/json?show=torrent&id=900":
            return {
                "title": "[Group] Solo Leveling Batch",
                "files": [
                    {
                        "filename": "[Group] Solo Leveling - 11.mkv",
                        "attachments": [{"id": 1, "type": "subtitle", "info": {"lang": "eng"}}],
                    },
                    {
                        "filename": "[Group] Solo Leveling - 12.mkv",
                        "attachments": [{"id": 2, "type": "subtitle", "info": {"lang": "eng"}}],
                    },
                ],
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = AnimeToshoProvider(_config(api_key=None))
    results = provider.search("Solo Leveling", "en", season=1, episode=12, tvdb_id=389597)

    assert results == [
        SubtitleSearchResult(
            release_name="[Group] Solo Leveling Batch", download_id="2", language="en"
        )
    ]


def test_animetosho_search_returns_empty_list_when_no_anidb_mapping(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"<anime-list />", request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeToshoProvider(_config())

    assert provider.search("Solo Leveling", "en", season=1, episode=12, tvdb_id=389597) == []


def test_animetosho_search_returns_empty_list_when_daily_quota_exceeded(monkeypatch):
    monkeypatch.setattr(animetosho, "_daily_quota_date", date.today())
    monkeypatch.setattr(animetosho, "_daily_quota_count", animetosho._DAILY_QUOTA_LIMIT)

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        if "raw.githubusercontent.com" in path:
            return httpx.Response(200, content=_MAPPING_XML, request=httpx.Request(method, path))
        raise AssertionError(f"AniDB API should not be called once quota is exceeded: {path}")

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeToshoProvider(_config())

    assert provider.search("Solo Leveling", "en", season=1, episode=12, tvdb_id=389597) == []


def test_animetosho_search_returns_matching_subtitle(monkeypatch):
    monkeypatch.setattr(ProviderHttpClient, "request", _mapping_and_anidb_response)

    def _get_json(self, path):
        if path == "/json?eid=277518":
            return [
                {
                    "id": 608526,
                    "title": "[EMBER] Solo Leveling - 12",
                    "timestamp": 1,
                    "status": "complete",
                }
            ]
        if path == "/json?show=torrent&id=608526":
            return {
                "title": "[EMBER] Solo Leveling - 12",
                "files": [
                    {
                        "attachments": [
                            {"id": 1961547, "type": "subtitle", "info": {"lang": "eng"}},
                            {"id": 1, "type": "other", "info": {}},
                        ]
                    }
                ],
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)

    provider = AnimeToshoProvider(_config())
    results = provider.search("Solo Leveling", "en", season=1, episode=12, tvdb_id=389597)

    assert results == [
        SubtitleSearchResult(
            release_name="[EMBER] Solo Leveling - 12", download_id="1961547", language="en"
        )
    ]


def test_animetosho_download_decompresses_xz_payload(monkeypatch):
    payload = lzma.compress(b"1\n00:00:00,000 --> 00:00:01,000\nHello\n")

    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=payload, request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeToshoProvider(_config())
    result = provider.download(
        SubtitleSearchResult(
            release_name="Solo Leveling - 12", download_id="1961547", language="en"
        )
    )

    assert result == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"


def test_animetosho_download_raises_when_the_download_fails(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(404, content=b"", request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeToshoProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Solo Leveling - 12", download_id="1961547", language="en"
            )
        )


def test_animetosho_download_raises_when_the_archive_is_not_xz(monkeypatch):
    def _request(self, method, path, data=None, json=None, headers=None, follow_redirects=False):
        return httpx.Response(200, content=b"not xz", request=httpx.Request(method, path))

    monkeypatch.setattr(ProviderHttpClient, "request", _request)

    provider = AnimeToshoProvider(_config())

    with pytest.raises(ProviderClientError):
        provider.download(
            SubtitleSearchResult(
                release_name="Solo Leveling - 12", download_id="1961547", language="en"
            )
        )
