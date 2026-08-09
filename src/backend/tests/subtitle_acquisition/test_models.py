import pytest
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig


@pytest.mark.parametrize(
    "kind,api_key,username,password,expected",
    [
        ("opensubtitles", None, None, None, False),
        ("opensubtitles", "key", None, None, True),
        ("addic7ed", None, None, None, False),
        ("addic7ed", None, "user", None, False),
        ("addic7ed", None, "user", "pass", True),
        ("yify_subtitles", None, None, None, True),
        ("tvsubtitles", None, None, None, True),
        ("napiprojekt", None, None, None, True),
    ],
)
def test_has_credentials(kind, api_key, username, password, expected):
    provider = SubtitleProviderConfig(
        kind=kind, api_key=api_key, username=username, password=password
    )

    assert provider.has_credentials is expected


@pytest.mark.parametrize(
    "kind,api_key,connection_verified,expected",
    [
        ("opensubtitles", None, False, False),
        ("opensubtitles", "key", False, True),  # credentialed kinds don't need a test
        ("opensubtitles", "key", True, True),
        ("napiprojekt", None, False, False),  # no credential, but never tested successfully
        ("napiprojekt", None, True, True),
    ],
)
def test_is_configured(kind, api_key, connection_verified, expected):
    provider = SubtitleProviderConfig(
        kind=kind, api_key=api_key, connection_verified=connection_verified
    )

    assert provider.is_configured is expected
