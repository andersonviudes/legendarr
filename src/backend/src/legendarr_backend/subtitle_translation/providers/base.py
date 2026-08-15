from typing import Protocol


class TranslationProvider(Protocol):
    """Contract every translation backend (DeepL, Google, LibreTranslate, ...) must satisfy."""

    name: str

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]: ...
