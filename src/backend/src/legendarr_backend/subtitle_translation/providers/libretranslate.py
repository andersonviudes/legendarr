from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


class LibreTranslateTranslationProvider:
    """Real LibreTranslate `translate()` backend for a configured `TranslationProviderConfig`.

    `api_key` is optional — only instances that opt into requiring one enforce it, same
    caveat as `connection_tests._test_libretranslate`.
    """

    name = "libretranslate"

    def __init__(self, config: TranslationProviderConfig) -> None:
        assert config.endpoint is not None
        self._endpoint = config.endpoint
        self._api_key = config.api_key

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        client = ProviderHttpClient("LibreTranslate", self._endpoint)
        payload = {
            "q": text,
            "source": source_language,
            "target": target_language,
            "format": "text",
        }
        if self._api_key:
            payload["api_key"] = self._api_key
        try:
            response = client.post_json("/translate", payload)
        finally:
            client.close()
        return response["translatedText"]
