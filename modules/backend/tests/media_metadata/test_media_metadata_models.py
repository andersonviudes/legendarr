import pytest
from legendarr_backend.media_metadata.models import MetadataProviderConfig


@pytest.mark.parametrize(
    "api_key,expected",
    [
        (None, False),
        ("a-key", True),
    ],
)
def test_has_credentials(api_key, expected):
    provider = MetadataProviderConfig(kind="tvdb", api_key=api_key)

    assert provider.has_credentials is expected


def test_is_configured_mirrors_has_credentials():
    assert MetadataProviderConfig(kind="tvdb", api_key=None).is_configured is False
    assert MetadataProviderConfig(kind="tvdb", api_key="key").is_configured is True
