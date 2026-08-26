from legendarr_backend.media_servers.client_factory import build_media_server_provider
from legendarr_backend.media_servers.models import MediaServerConfig
from legendarr_backend.media_servers.providers.jellyfin import JellyfinMediaServerProvider
from legendarr_backend.media_servers.providers.plex import PlexMediaServerProvider


def test_build_media_server_provider_plex():
    provider = build_media_server_provider(
        MediaServerConfig(kind="plex", base_url="http://plex.local:32400", token="tok")
    )

    assert isinstance(provider, PlexMediaServerProvider)


def test_build_media_server_provider_jellyfin():
    provider = build_media_server_provider(
        MediaServerConfig(kind="jellyfin", base_url="http://jellyfin.local:8096", token="tok")
    )

    assert isinstance(provider, JellyfinMediaServerProvider)
