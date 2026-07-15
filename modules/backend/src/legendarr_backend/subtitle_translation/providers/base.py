from typing import Protocol


class TranslationProvider(Protocol):
    """Contract every translation backend (DeepL, Google, LibreTranslate, ...) must satisfy."""

    name: str

    def translate(self, text: str, source_language: str, target_language: str) -> str: ...
