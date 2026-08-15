"""Per-provider "test connection" checks for `TranslationProviderConfig`.

Mirrors `legendarr_backend.subtitle_acquisition.connection_tests` — this is deliberately not
the `translate()` call itself, each function here only answers "is this reachable/
authenticated," not "translate this text." Endpoints below were confirmed against each
provider's official API docs.
"""

from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
)
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.llm import DEFAULT_LLM_ENDPOINT

ConnectionTestResult = tuple[bool, str]


def test_connection(config: TranslationProviderConfig) -> ConnectionTestResult:
    """Dispatch to the connection check for `config.kind`. Returns `(success, message)`,
    the same shape as `subtitle_acquisition/connection_tests.py`'s `test_connection`."""
    tester = _TESTERS.get(config.kind)
    if tester is None:
        return False, f"Unknown provider kind: {config.kind}"
    return tester(config)


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
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    assert config.api_key is not None
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


def _test_llm(config: TranslationProviderConfig) -> ConnectionTestResult:
    if (error := _require(config.api_key, "An API Key")) is not None:
        return False, error
    endpoint = config.endpoint or DEFAULT_LLM_ENDPOINT
    client = ProviderHttpClient(
        "LLM", endpoint, headers={"Authorization": f"Bearer {config.api_key}"}
    )
    try:
        client.get_json("/models")
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()
    return True, "Connection successful"


_TESTERS = {
    "deepl": _test_deepl,
    "google": _test_google,
    "libretranslate": _test_libretranslate,
    "llm": _test_llm,
}
