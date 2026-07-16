from legendarr_backend.bootstrap import _build_media_clients
from legendarr_backend.media_providers.radarr_client import RadarrClient
from legendarr_backend.media_providers.sonarr_client import SonarrClient
from legendarr_backend.shared_kernel.config.config_file import AppConfigFile


def test_build_media_clients_constructs_configured_clients():
    config = AppConfigFile(
        radarr_url="http://radarr:7878",
        radarr_api_key="radarr-key",
        sonarr_url="http://sonarr:8989",
        sonarr_api_key="sonarr-key",
    )

    radarr, sonarr = _build_media_clients(config)

    assert isinstance(radarr, RadarrClient)
    assert isinstance(sonarr, SonarrClient)


def test_build_media_clients_skips_unconfigured_clients():
    config = AppConfigFile()

    radarr, sonarr = _build_media_clients(config)

    assert radarr is None
    assert sonarr is None
