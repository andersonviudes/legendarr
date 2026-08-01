from datetime import UTC, datetime

from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.http_client.client import ProviderHttpClient


def test_list_items_maps_response_to_media_items(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: [
            {
                "id": 1,
                "title": "Series",
                "path": "/series/series",
                "tvdbId": 121361,
                "imdbId": "tt0944947",
            }
        ],
    )
    client = SonarrClient("http://sonarr.local", "api-key")

    items = client.list_items()

    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].title == "Series"
    assert items[0].path == "/series/series"
    assert items[0].tvdb_id == 121361
    assert items[0].imdb_id == "tt0944947"


def test_system_status_requests_system_status(monkeypatch):
    requested_paths = []

    def _get_json(self, path):
        requested_paths.append(path)
        return {"appName": "Sonarr"}

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = SonarrClient("http://sonarr.local", "api-key")

    assert client.system_status() == {"appName": "Sonarr"}
    assert requested_paths == ["/api/v3/system/status"]


def test_list_recent_import_ids_maps_series_ids(monkeypatch):
    requested_paths = []

    def _get_json(self, path):
        requested_paths.append(path)
        return {
            "records": [
                {"seriesId": 3, "date": "2026-07-26T10:00:00Z"},
                {"seriesId": 5, "date": "2026-07-26T09:00:00Z"},
                {"seriesId": 8, "date": "2026-07-20T10:00:00Z"},
            ]
        }

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = SonarrClient("http://sonarr.local", "api-key")

    ids = client.list_recent_import_ids(datetime(2026, 7, 26, tzinfo=UTC))

    assert sorted(ids) == [3, 5]
    assert requested_paths[0].startswith("/api/v3/history?eventType=3")
