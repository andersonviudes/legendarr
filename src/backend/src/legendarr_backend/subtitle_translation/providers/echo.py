class EchoTranslationProvider:
    """Development-only provider that returns the source text unchanged.

    Useful for exercising the translation pipeline before a real provider
    (DeepL, Google Cloud Translate, OpenAI, LibreTranslate, ...) is configured.
    """

    name = "echo"

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        return text
