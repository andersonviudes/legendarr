from legendarr_backend.media_metadata.client_factory import build_metadata_provider
from legendarr_backend.media_metadata.models import MetadataProviderConfig
from legendarr_backend.media_metadata.providers.imdb import OmdbMetadataProvider
from legendarr_backend.media_metadata.providers.tvdb import TvdbMetadataProvider


def test_build_metadata_provider_tvdb():
    provider = build_metadata_provider(MetadataProviderConfig(kind="tvdb", api_key="key"))

    assert isinstance(provider, TvdbMetadataProvider)


def test_build_metadata_provider_imdb():
    provider = build_metadata_provider(MetadataProviderConfig(kind="imdb", api_key="key"))

    assert isinstance(provider, OmdbMetadataProvider)
