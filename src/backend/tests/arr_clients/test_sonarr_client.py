from datetime import UTC, datetime

from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.http_client.client import ProviderHttpClient


def test_list_items_maps_response_to_media_items(monkeypatch):
    def _get_json(self, path):
        if path == "/api/v3/qualityprofile":
            return [{"id": 4, "name": "Any"}]
        return [
            {
                "id": 1,
                "title": "Series",
                "path": "/series/series",
                "tvdbId": 121361,
                "imdbId": "tt0944947",
                "monitored": True,
                "status": "continuing",
                "qualityProfileId": 4,
                "statistics": {"episodeCount": 8, "episodeFileCount": 8},
                "genres": ["Anime", "Adventure"],
                "previousAiring": "2018-06-10T01:00:00Z",
            }
        ]

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = SonarrClient("http://sonarr.local", "api-key")

    items = client.list_items()

    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].title == "Series"
    assert items[0].path == "/series/series"
    assert items[0].tvdb_id == 121361
    assert items[0].imdb_id == "tt0944947"
    assert items[0].monitored is True
    assert items[0].status == "continuing"
    assert items[0].quality_profile_id == 4
    assert items[0].quality_profile_name == "Any"
    assert items[0].episode_count == 8
    assert items[0].episode_file_count == 8
    assert items[0].genres == ["Anime", "Adventure"]
    assert items[0].last_aired == datetime(2018, 6, 10, 1, 0, tzinfo=UTC)


def test_list_items_defaults_genres_and_last_aired_when_absent(monkeypatch):
    def _get_json(self, path):
        if path == "/api/v3/qualityprofile":
            return []
        return [{"id": 1, "title": "Series", "path": "/series/series"}]

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = SonarrClient("http://sonarr.local", "api-key")

    items = client.list_items()

    assert items[0].genres == []
    assert items[0].last_aired is None


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


def test_list_episodes_maps_response_to_episode_items(monkeypatch):
    requested_paths = []

    def _get_json(self, path):
        requested_paths.append(path)
        return [
            {
                "seasonNumber": 3,
                "episodeNumber": 7,
                "title": "The Dragon in Winter",
                "hasFile": True,
                "episodeFile": {"relativePath": "Season 03/House.S03E07.mkv"},
            },
            {
                "seasonNumber": 3,
                "episodeNumber": 8,
                "title": "TBA",
                "hasFile": False,
            },
        ]

    monkeypatch.setattr(ProviderHttpClient, "get_json", _get_json)
    client = SonarrClient("http://sonarr.local", "api-key")

    episodes = client.list_episodes(1)

    assert requested_paths == ["/api/v3/episode?seriesId=1&includeEpisodeFile=true"]
    assert episodes[0].season_number == 3
    assert episodes[0].episode_number == 7
    assert episodes[0].title == "The Dragon in Winter"
    assert episodes[0].relative_path == "Season 03/House.S03E07.mkv"
    assert episodes[1].relative_path is None
