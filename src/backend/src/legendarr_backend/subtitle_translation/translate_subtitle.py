from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider


def translate_subtitle(
    lines: list[SubtitleLine],
    provider: TranslationProvider,
    source_language: str,
    target_language: str,
) -> list[SubtitleLine]:
    """Translate every line of a subtitle, preserving timing."""
    translated_texts = provider.translate_batch(
        [line.text for line in lines], source_language, target_language
    )
    return [
        SubtitleLine(
            index=line.index,
            start_ms=line.start_ms,
            end_ms=line.end_ms,
            text=translated_text,
        )
        for line, translated_text in zip(lines, translated_texts, strict=True)
    ]
