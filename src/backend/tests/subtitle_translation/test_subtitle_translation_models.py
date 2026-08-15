import pytest
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


@pytest.mark.parametrize(
    "kind,api_key,endpoint,expected",
    [
        ("deepl", None, None, False),
        ("deepl", "key", None, True),
        ("google", None, None, False),
        ("google", "key", None, True),
        ("libretranslate", None, None, False),
        ("libretranslate", None, "http://localhost:5000", True),
        ("llm", None, None, False),
        ("llm", "key", None, True),
    ],
)
def test_has_credentials(kind, api_key, endpoint, expected):
    provider = TranslationProviderConfig(kind=kind, api_key=api_key, endpoint=endpoint)

    assert provider.has_credentials is expected


@pytest.mark.parametrize(
    "kind,api_key,endpoint",
    [
        ("deepl", "key", None),
        ("google", "key", None),
        ("libretranslate", None, "http://localhost:5000"),
        ("llm", "key", None),
    ],
)
def test_is_configured_mirrors_has_credentials(kind, api_key, endpoint):
    provider = TranslationProviderConfig(kind=kind, api_key=api_key, endpoint=endpoint)

    assert provider.is_configured is provider.has_credentials


def test_is_configured_false_without_credentials():
    provider = TranslationProviderConfig(kind="deepl")

    assert provider.is_configured is False
