from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider


def translate_subtitle(
    lines: list[SubtitleLine],
    provider: TranslationProvider,
    source_language: str,
    target_language: str,
) -> list[SubtitleLine]:
    """Translate every line of a subtitle, preserving timing."""
    return [
        SubtitleLine(
            index=line.index,
            start_ms=line.start_ms,
            end_ms=line.end_ms,
            text=provider.translate(line.text, source_language, target_language),
        )
        for line in lines
    ]
