from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.media_library.providers.radarr_client import RadarrClient


def test_list_items_maps_response_to_media_items(monkeypatch):
    monkeypatch.setattr(
        ProviderHttpClient,
        "get_json",
        lambda self, path: [{"id": 1, "title": "Movie", "path": "/movies/movie"}],
    )
    client = RadarrClient("http://radarr.local", "api-key")

    items = client.list_items()

    assert len(items) == 1
    assert items[0].id == 1
    assert items[0].title == "Movie"
    assert items[0].path == "/movies/movie"
