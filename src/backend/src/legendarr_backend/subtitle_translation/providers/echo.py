class EchoTranslationProvider:
    """Development-only provider that returns the source text unchanged.

    Useful for exercising the translation pipeline before a real provider
    (DeepL, Google Cloud Translate, OpenAI, LibreTranslate, ...) is configured.
    """

    name = "echo"

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        return list(texts)
