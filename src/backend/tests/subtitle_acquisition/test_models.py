import pytest
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig


@pytest.mark.parametrize(
    "kind,api_key,username,password,expected",
    [
        ("opensubtitles", None, None, None, False),
        ("opensubtitles", None, "user", None, False),
        ("opensubtitles", None, "user", "pass", True),
        ("addic7ed", None, None, None, False),
        ("addic7ed", None, "user", None, False),
        ("addic7ed", None, "user", "pass", True),
        ("yify_subtitles", None, None, None, True),
        ("tvsubtitles", None, None, None, True),
        ("napiprojekt", None, None, None, True),
        # animetosho's api_key is optional, not required — see models.py's
        # `_API_KEY_KINDS` comment.
        ("animetosho", None, None, None, True),
        ("animetosho", "key", None, None, True),
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
        ("napiprojekt", None, False, False),  # no credential, but never tested successfully
        ("napiprojekt", None, True, True),
        # Same shape as napiprojekt: animetosho's api_key is optional, so it's still
        # gated on a successful "Test connection" rather than the credential alone.
        ("animetosho", None, False, False),
        ("animetosho", None, True, True),
        ("animetosho", "key", False, False),
    ],
)
def test_is_configured(kind, api_key, connection_verified, expected):
    provider = SubtitleProviderConfig(
        kind=kind, api_key=api_key, connection_verified=connection_verified
    )

    assert provider.is_configured is expected


@pytest.mark.parametrize(
    "username,password,connection_verified,expected",
    [
        (None, None, False, False),
        ("user", "pass", False, True),  # credentialed kinds don't need a test
        ("user", "pass", True, True),
    ],
)
def test_is_configured_for_a_username_password_kind(
    username, password, connection_verified, expected
):
    provider = SubtitleProviderConfig(
        kind="opensubtitles",
        username=username,
        password=password,
        connection_verified=connection_verified,
    )

    assert provider.is_configured is expected


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("opensubtitles", True),
        ("addic7ed", True),
        ("subdl", True),
        ("napiprojekt", False),
        ("yify_subtitles", False),
        # animetosho has a real, displayed `api_key` field, but it's optional — same
        # no-credential-required group as napiprojekt, not the api-key/username-password
        # groups above. See models.py's `_API_KEY_KINDS` comment.
        ("animetosho", False),
    ],
)
def test_credentials_required(kind, expected):
    provider = SubtitleProviderConfig(kind=kind)

    assert provider.credentials_required is expected
