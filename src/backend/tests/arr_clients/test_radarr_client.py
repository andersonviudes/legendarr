from datetime import UTC, datetime

from legendarr_backend.arr_clients.radarr_client import RadarrClient
from legendarr_backend.http_client.client import ProviderHttpClient


def test_list_items_maps_response_to_media_items(monkeypatch):
    def _get_json(self, path):
        if path == "/api/v3/qualityprofile":
            return [{"id": 4, "name": "Any"}]
        return [
            {
                "id": 1,
                "title": "Movie",
                "path": "/movies/movie",
                "imdbId": "tt1234567",
                "monitored": True,
                "status": "released",
                "qualityProfileId": 4,
                "genres": ["Action", "Sci-Fi"],
            }
        ]

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = RadarrClient("http://radarr.local", "api-key")

    items = client.list_items()

    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].title == "Movie"
    assert items[0].path == "/movies/movie"
    # Radarr's API has no `tvdbId` field (its own canonical id system is TMDb).
    assert items[0].tvdb_id is None
    assert items[0].imdb_id == "tt1234567"
    assert items[0].monitored is True
    assert items[0].status == "released"
    assert items[0].quality_profile_id == 4
    assert items[0].quality_profile_name == "Any"
    assert items[0].genres == ["Action", "Sci-Fi"]


def test_system_status_requests_system_status(monkeypatch):
    requested_paths = []

    def _get_json(self, path):
        requested_paths.append(path)
        return {"appName": "Radarr"}

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = RadarrClient("http://radarr.local", "api-key")

    assert client.system_status() == {"appName": "Radarr"}
    assert requested_paths == ["/api/v3/system/status"]


def test_list_recent_import_ids_filters_by_since_and_dedupes(monkeypatch):
    requested_paths = []

    def _get_json(self, path):
        requested_paths.append(path)
        return {
            "records": [
                {"movieId": 1, "date": "2026-07-26T10:00:00Z"},
                {"movieId": 1, "date": "2026-07-26T11:00:00Z"},
                {"movieId": 2, "date": "2026-07-25T10:00:00Z"},
            ]
        }

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = RadarrClient("http://radarr.local", "api-key")

    ids = client.list_recent_import_ids(datetime(2026, 7, 26, tzinfo=UTC))

    assert ids == [1]
    assert len(requested_paths) == 1
    assert requested_paths[0].startswith("/api/v3/history?eventType=3")
