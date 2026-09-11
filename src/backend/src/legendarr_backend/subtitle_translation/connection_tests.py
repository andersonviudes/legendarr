"""Per-provider "test connection" checks for `TranslationProviderConfig`.

Mirrors `legendarr_backend.subtitle_acquisition.connection_tests` — this is deliberately not
the `translate()` call itself, each function here only answers "is this reachable/
authenticated," not "translate this text." Endpoints below were confirmed against each
provider's official API docs.

`google` in its keyless mode is the one exception: the public `translate_a/single` endpoint
is the only thing there is to probe — no `/languages`, no credential to validate — so that
check really does translate one word.
"""

from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
)
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.plugins import plugin_provider_classes
from legendarr_backend.subtitle_translation.providers.gemini import GEMINI_ENDPOINT
from legendarr_backend.subtitle_translation.providers.google import (
    GoogleFreeTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.llm import DEFAULT_LLM_ENDPOINT

ConnectionTestResult = tuple[bool, str]


def test_connection(config: TranslationProviderConfig) -> ConnectionTestResult:
    """Dispatch to the connection check for `config.kind`. Returns `(success, message)`,
    the same shape as `subtitle_acquisition/connection_tests.py`'s `test_connection`.

    A dynamically-loaded plugin (ROADMAP.md 0.9.0) may define its own `test_connection`
    static/classmethod with this same signature; one that doesn't gets a generic
    "configuration saved" result instead of "Unknown provider kind" — the plugin loaded
    and is usable, it just has nothing to probe.
    """
    tester = _TESTERS.get(config.kind)
    if tester is not None:
        return tester(config)
    plugin_class = plugin_provider_classes().get(config.kind)
    if plugin_class is None:
        return False, f"Unknown provider kind: {config.kind}"
    plugin_tester = getattr(plugin_class, "test_connection", None)
    if plugin_tester is None:
        return True, "No connection test available for this provider — configuration saved."
    return plugin_tester(config)


def _require(value: str | None, label: str) -> str | None:
    if not value:
        return f"{label} is required"
    return None


def _test_deepl(config: TranslationProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
    # Free-tier keys are suffixed `:fx` and only work against the api-free host, per DeepL's
    # own docs (https://developers.deepl.com/docs/api-reference/usage-and-quota) — a Pro key
    # against api-free.deepl.com (or vice versa) gets rejected outright.
    is_free_key = config.api_key.endswith(":fx")
    host = "https://api-free.deepl.com" if is_free_key else "https://api.deepl.com"
    client = ProviderHttpClient(
        "DeepL", host, headers={"Authorization": f"DeepL-Auth-Key {config.api_key}"}
    )
    try:
        client.get_json("/v2/usage")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_google(config: TranslationProviderConfig) -> ConnectionTestResult:
    # No API Key means the keyless public endpoint, which has no credential to check.
    if not config.api_key:
        return _test_google_free(config)
    client = ProviderHttpClient("Google Translate", "https://translation.googleapis.com")
    try:
        client.get_json(f"/language/translate/v2/languages?key={config.api_key}")
    except ProviderClientError as exc:
        # Google's v2 API takes the key as a query param (no header option), so
        # `describe_error`'s fallback (`str(exc)`, which embeds the request URL) can leak
        # it back into the "Test connection" response — redact before returning.
        return False, describe_error(exc).replace(config.api_key, "***")
    finally:
        client.close()
    return True, "Connection successful"


def _test_google_free(config: TranslationProviderConfig) -> ConnectionTestResult:
    """Translate one word through the real keyless backend. Going through
    `GoogleFreeTranslationProvider` rather than hand-rolling the request keeps the probe
    honest: it exercises the same URL shape, user-agent and response parsing a real
    translation would, so a "Connection successful" here means the endpoint still answers
    *us*, not just that the host is up.
    """
    try:
        GoogleFreeTranslationProvider(config).translate_batch(["Hello"], "en", "es")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    except Exception as exc:
        # An endpoint change that breaks the response parsing should read as a failed
        # test, not as a 500 on the route.
        return False, f"Google Translate returned an unexpected response: {exc}"
    return True, "Connection successful"


def _test_libretranslate(config: TranslationProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.endpoint, "An Endpoint URL")) is not None:
        return False, error
    assert config.endpoint is not None
    # Self-hosted, so the base URL comes from the user, not a fixed host. `/languages` needs
    # no credential on a stock instance — the API Key (when set) is only enforced on
    # `/translate` by instances that opt into it, so this only proves the instance answers.
    client = ProviderHttpClient("LibreTranslate", config.endpoint)
    try:
        client.get_json("/languages")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_openai_compatible(
    config: TranslationProviderConfig, label: str, default_endpoint: str
) -> ConnectionTestResult:
    """Shared `/models` probe for every kind speaking the OpenAI protocol — `llm` and
    `gemini` differ only in which endpoint a blank config falls back to."""
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    endpoint = config.endpoint or default_endpoint
    client = ProviderHttpClient(
        label, endpoint, headers={"Authorization": f"Bearer {config.api_key}"}
    )
    try:
        client.get_json("/models")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _test_llm(config: TranslationProviderConfig) -> ConnectionTestResult:
    return _test_openai_compatible(config, "LLM", DEFAULT_LLM_ENDPOINT)


def _test_gemini(config: TranslationProviderConfig) -> ConnectionTestResult:
    return _test_openai_compatible(config, "Gemini", GEMINI_ENDPOINT)


_TESTERS = {
    "deepl": _test_deepl,
    "gemini": _test_gemini,
    "google": _test_google,
    "libretranslate": _test_libretranslate,
    "llm": _test_llm,
}
