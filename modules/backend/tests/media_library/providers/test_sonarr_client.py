from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.media_library.providers.sonarr_client import SonarrClient


def test_list_items_maps_response_to_media_items(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: [{"id": 1, "title": "Series", "path": "/series/series"}],
    )
    client = SonarrClient("http://sonarr.local", "api-key")

    items = client.list_items()

    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].title == "Series"
    assert items[0].path == "/series/series"
