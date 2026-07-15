from dataclasses import dataclass

from legendarr_backend.media_providers.radarr_client import RadarrClient
from legendarr_backend.media_providers.sonarr_client import SonarrClient


@dataclass(frozen=True)
class SyncResult:
    movies_synced: int
    series_synced: int


def sync_media_library(radarr: RadarrClient | None, sonarr: SonarrClient | None) -> SyncResult:
    """Pull the current libraries from Radarr and Sonarr.

    This is the single entry point the scheduler and the web UI call to
    refresh what media legendarr knows about; persistence of the results
    will land here as the feature grows.
    """
    movies = radarr.list_movies() if radarr else []
    series = sonarr.list_series() if sonarr else []
    return SyncResult(movies_synced=len(movies), series_synced=len(series))
