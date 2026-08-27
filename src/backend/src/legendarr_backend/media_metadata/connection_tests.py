"""Per-provider "test connection" checks for `MetadataProviderConfig`.

Same shape as `subtitle_acquisition/connection_tests.py`: each function only answers "is
this reachable/authenticated," reusing the real provider clients `fetch_metadata.py` uses
for actual lookups, against a fixed well-known id from each catalog.
"""

from legendarr_backend.http_client.client import ProviderClientError, describe_error
from legendarr_backend.media_metadata.models import MetadataProviderConfig
from legendarr_backend.media_metadata.providers.imdb import OmdbMetadataProvider
from legendarr_backend.media_metadata.providers.tmdb import TmdbMetadataProvider
from legendarr_backend.media_metadata.providers.tvdb import TvdbMetadataProvider

ConnectionTestResult = tuple[bool, str]

_TVDB_TEST_SERIES_ID = 121361  # Game of Thrones — a permanent id, unlikely to ever move
_IMDB_TEST_ID = "tt0111161"  # The Shawshank Redemption — shared with the TMDb test below,
# which looks the same title up by imdb id via TMDb's `/find` endpoint


def test_connection(config: MetadataProviderConfig) -> ConnectionTestResult:
    """Dispatch to the connection check for `config.kind`. Returns `(success, message)`,
    the same shape as `subtitle_acquisition/connection_tests.py`'s `test_connection`."""
    tester = _TESTERS.get(config.kind)
    if tester is None:
        return False, f"Unknown metadata provider kind: {config.kind}"
    return tester(config)


def _require(value: str | None, label: str) -> str | None:
    if not value:
        return f"{label} is required"
    return None


def _test_tvdb(config: MetadataProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
    provider = TvdbMetadataProvider(config.api_key)
    try:
        result = provider.fetch(
            media_type="series", title="", tvdb_id=_TVDB_TEST_SERIES_ID, imdb_id=None
        )
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        provider.close()
    if result is None:
        return False, "Connection succeeded but the test lookup returned nothing"
    return True, "Connection successful"


def _test_imdb(config: MetadataProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
    provider = OmdbMetadataProvider(config.api_key)
    try:
        result = provider.fetch(media_type="movie", title="", tvdb_id=None, imdb_id=_IMDB_TEST_ID)
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        provider.close()
    if result is None:
        return False, "The server rejected the API Key"
    return True, "Connection successful"


def _test_tmdb(config: MetadataProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
    provider = TmdbMetadataProvider(config.api_key)
    try:
        result = provider.fetch(media_type="movie", title="", tvdb_id=None, imdb_id=_IMDB_TEST_ID)
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        provider.close()
    if result is None:
        return False, "Connection succeeded but the test lookup returned nothing"
    return True, "Connection successful"


_TESTERS = {"tvdb": _test_tvdb, "imdb": _test_imdb, "tmdb": _test_tmdb}
