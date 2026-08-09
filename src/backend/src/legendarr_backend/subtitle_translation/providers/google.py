from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


class GoogleTranslationProvider:
    """Real Google Cloud Translation (v2) `translate()` backend for a configured
    `TranslationProviderConfig`.
    """

    name = "google"

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        client = ProviderHttpClient("Google Translate", "https://translation.googleapis.com")
        try:
            response = client.post_json(
                f"/language/translate/v2?key={self._api_key}",
                {
                    "q": text,
                    "source": source_language,
                    "target": target_language,
                    "format": "text",
                },
            )
        finally:
            client.close()
        return response["data"]["translations"][0]["translatedText"]
