import pytest
from legendarr_backend.config.settings import Settings
from legendarr_backend.subtitle_translation import plugins
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


class _FixturePlugin:
    kind = "fixture-plugin"
    label = "Fixture Plugin"
    name = "fixture-plugin"
    credential_fields = ("api_key", "endpoint")
    required_credential_fields = ("api_key",)
    plugin_api_version = plugins.SUPPORTED_PLUGIN_API_VERSION

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._config = config

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        return texts


@pytest.fixture(autouse=True)
def _clear_plugin_cache():
    plugins.load_plugin_providers.cache_clear()
    yield
    plugins.load_plugin_providers.cache_clear()


@pytest.fixture
def _loaded_plugin(monkeypatch):
    monkeypatch.setattr(
        plugins,
        "get_settings",
        lambda: Settings(translation_plugin_packages=f"{__name__}:_FixturePlugin"),
    )


@pytest.mark.parametrize(
    "kind,api_key,endpoint,expected",
    [
        ("deepl", None, None, False),
        ("deepl", "key", None, True),
        # `google` needs nothing: a blank key means the keyless public endpoint, not
        # "not configured yet".
        ("google", None, None, True),
        ("google", "key", None, True),
        ("gemini", None, None, False),
        ("gemini", "key", None, True),
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
        ("google", None, None),
        ("gemini", "key", None),
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


def test_has_credentials_for_a_loaded_plugin(_loaded_plugin):
    without_key = TranslationProviderConfig(kind="fixture-plugin")
    with_key = TranslationProviderConfig(kind="fixture-plugin", api_key="key")

    assert without_key.has_credentials is False
    assert with_key.has_credentials is True


def test_has_credentials_true_for_an_unrecognized_kind():
    """No plugin loaded for this kind — same "no credential concept" fallback a
    reachability-only kind would hit, rather than gating on nothing."""
    provider = TranslationProviderConfig(kind="not-a-real-kind")

    assert provider.has_credentials is True


def test_label_and_credential_fields_for_built_in_kinds():
    provider = TranslationProviderConfig(kind="llm")

    assert provider.label == "LLM (OpenAI-compatible)"
    assert provider.credential_fields == ("endpoint", "api_key", "model", "prompt_template")


def test_gemini_has_no_endpoint_field():
    """Gemini is pinned to Google AI Studio's OpenAI-compatible URL, so the form never
    offers an Endpoint to override it with."""
    provider = TranslationProviderConfig(kind="gemini")

    assert provider.label == "Gemini (Google AI Studio)"
    assert provider.credential_fields == ("api_key", "model", "prompt_template")


@pytest.mark.parametrize(
    "kind,expected",
    [("google", True), ("deepl", False), ("gemini", False), ("libretranslate", False)],
)
def test_credentials_optional(kind, expected):
    """`google` renders an API Key field it doesn't need — the provider grid captions that
    card differently so it doesn't claim credentials are required."""
    assert TranslationProviderConfig(kind=kind).credentials_optional is expected


def test_credentials_optional_is_false_for_a_kind_with_no_fields_to_render():
    """Nothing to caption — a kind with no credential fields at all already gets its own
    "run test to enable" line, so this must not claim to be the optional-credentials case."""
    assert TranslationProviderConfig(kind="not-a-real-kind").credentials_optional is False


def test_label_and_credential_fields_for_a_loaded_plugin(_loaded_plugin):
    provider = TranslationProviderConfig(kind="fixture-plugin")

    assert provider.label == "Fixture Plugin"
    assert provider.credential_fields == ("api_key", "endpoint")


def test_label_falls_back_to_kind_for_an_unrecognized_kind():
    provider = TranslationProviderConfig(kind="not-a-real-kind")

    assert provider.label == "not-a-real-kind"
    assert provider.credential_fields == ()
