"""Per-kind "test connection" checks for `MediaServerConfig`.

Each function only answers "is this reachable/authenticated" against a read-only
endpoint — never `notify_subtitle_written`, which would trigger a real refresh/scan on
the user's server as a side effect of clicking "Test connection".
"""

from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
)
from legendarr_backend.media_servers.models import MediaServerConfig

ConnectionTestResult = tuple[bool, str]


def test_connection(config: MediaServerConfig) -> ConnectionTestResult:
    """Dispatch to the connection check for `config.kind`. Returns `(success, message)`,
    the same shape as `media_metadata/connection_tests.py`'s `test_connection`."""
    tester = _TESTERS.get(config.kind)
    if tester is None:
        return False, f"Unknown media server kind: {config.kind}"
    return tester(config)


def _require(value: str | None, label: str) -> str | None:
    if not value:
        return f"{label} is required"
    return None


def _test_plex(config: MediaServerConfig) -> ConnectionTestResult:
    if (error := _require(config.base_url, "A base URL")) is not None:
        return False, error
    if (error := _require(config.token, "A Plex token")) is not None:
        return False, error
    assert config.base_url is not None
    assert config.token is not None
    client = ProviderHttpClient("Plex", config.base_url, headers={"X-Plex-Token": config.token})
    try:
        client.ping("/library/sections")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_jellyfin(config: MediaServerConfig) -> ConnectionTestResult:
    if (error := _require(config.base_url, "A base URL")) is not None:
        return False, error
    if (error := _require(config.token, "A Jellyfin API key")) is not None:
        return False, error
    assert config.base_url is not None
    assert config.token is not None
    client = ProviderHttpClient(
        "Jellyfin",
        config.base_url,
        headers={"Authorization": f'MediaBrowser Token="{config.token}"'},
    )
    try:
        client.ping("/System/Info")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


_TESTERS = {"plex": _test_plex, "jellyfin": _test_jellyfin}
