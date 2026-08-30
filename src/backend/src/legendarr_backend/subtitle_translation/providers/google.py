from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig

# Google Cloud Translation API v2 rejects a request with more than 128 `q` text
# segments ("Too many text segments") — a real subtitle routinely has more lines than
# that, so the batch has to be split into chunks of at most this size.
MAX_TEXT_SEGMENTS_PER_REQUEST = 128


class GoogleTranslationProvider:
    """Real Google Cloud Translation (v2) `translate()` backend for a configured
    `TranslationProviderConfig`.
    """

    name = "google"

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._api_key = config.api_key

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        client = ProviderHttpClient("Google Translate", "https://translation.googleapis.com")
        try:
            translated_texts = []
            for start in range(0, len(texts), MAX_TEXT_SEGMENTS_PER_REQUEST):
                chunk = texts[start : start + MAX_TEXT_SEGMENTS_PER_REQUEST]
                response = client.post_json(
                    f"/language/translate/v2?key={self._api_key}",
                    {
                        "q": chunk,
                        "source": source_language,
                        "target": target_language,
                        "format": "text",
                    },
                )
                translated_texts.extend(
                    translation["translatedText"]
                    for translation in response["data"]["translations"]
                )
        finally:
            client.close()
        return translated_texts
