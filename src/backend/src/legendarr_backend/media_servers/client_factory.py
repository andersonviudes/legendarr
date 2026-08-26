from legendarr_backend.media_servers.models import MediaServerConfig
from legendarr_backend.media_servers.providers.base import MediaServerProvider
from legendarr_backend.media_servers.providers.jellyfin import JellyfinMediaServerProvider
from legendarr_backend.media_servers.providers.plex import PlexMediaServerProvider

_PROVIDER_CLASSES = {"plex": PlexMediaServerProvider, "jellyfin": JellyfinMediaServerProvider}


def build_media_server_provider(config: MediaServerConfig) -> MediaServerProvider:
    assert config.base_url is not None
    assert config.token is not None
    return _PROVIDER_CLASSES[config.kind](config.base_url, config.token)
