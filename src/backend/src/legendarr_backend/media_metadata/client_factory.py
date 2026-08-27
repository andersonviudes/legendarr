from legendarr_backend.media_metadata.models import MetadataProviderConfig
from legendarr_backend.media_metadata.providers.base import MetadataProvider
from legendarr_backend.media_metadata.providers.imdb import OmdbMetadataProvider
from legendarr_backend.media_metadata.providers.tmdb import TmdbMetadataProvider
from legendarr_backend.media_metadata.providers.tvdb import TvdbMetadataProvider

_PROVIDER_CLASSES = {
    "tvdb": TvdbMetadataProvider,
    "imdb": OmdbMetadataProvider,
    "tmdb": TmdbMetadataProvider,
}


def build_metadata_provider(config: MetadataProviderConfig) -> MetadataProvider:
    return _PROVIDER_CLASSES[config.kind](config.api_key)
