import pytest
from legendarr_backend.media_servers.models import MediaServerConfig


@pytest.mark.parametrize(
    "base_url,token,expected",
    [
        (None, None, False),
        ("http://plex.local:32400", None, False),
        (None, "a-token", False),
        ("http://plex.local:32400", "a-token", True),
    ],
)
def test_has_credentials_requires_base_url_and_token(base_url, token, expected):
    server = MediaServerConfig(kind="plex", base_url=base_url, token=token)

    assert server.has_credentials is expected


def test_is_configured_mirrors_has_credentials():
    assert MediaServerConfig(kind="plex").is_configured is False
    configured = MediaServerConfig(kind="plex", base_url="http://plex.local:32400", token="tok")
    assert configured.is_configured is True


def test_new_row_defaults_to_disabled():
    assert MediaServerConfig(kind="plex").enabled is False
