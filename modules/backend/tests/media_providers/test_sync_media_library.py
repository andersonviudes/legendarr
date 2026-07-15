from legendarr_backend.media_providers.sync_media_library import sync_media_library


def test_sync_media_library_with_no_providers_returns_zero_counts():
    result = sync_media_library(radarr=None, sonarr=None)

    assert result.movies_synced == 0
    assert result.series_synced == 0
