from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


class DeepLTranslationProvider:
    """Real DeepL `translate()` backend, built from a configured `TranslationProviderConfig`.

    Same free-vs-pro host selection as `connection_tests._test_deepl` — a `:fx`-suffixed key
    only works against the api-free host.
    """

    name = "deepl"

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key
        is_free_key = (config.api_key or "").endswith(":fx")
        self._host = "https://api-free.deepl.com" if is_free_key else "https://api.deepl.com"

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient(
            "DeepL", self._host, headers={"Authorization": f"DeepL-Auth-Key {self._api_key}"}
        )
        try:
            response = client.post_json(
                "/v2/translate",
                {
                    "text": texts,
                    "source_lang": source_language.upper(),
                    "target_lang": target_language.upper(),
                },
            )
        finally:
            client.close()
        return [translation["text"] for translation in response["translations"]]
