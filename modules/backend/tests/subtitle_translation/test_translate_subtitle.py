from legendarr_backend.subtitle_translation.providers.echo import EchoTranslationProvider
from legendarr_backend.subtitle_translation.translate_subtitle import (
    SubtitleLine,
    translate_subtitle,
)


def test_translate_subtitle_preserves_timing_and_order():
    lines = [
        SubtitleLine(index=1, start_ms=0, end_ms=1000, text="hello"),
        SubtitleLine(index=2, start_ms=1000, end_ms=2000, text="world"),
    ]

    translated = translate_subtitle(lines, EchoTranslationProvider(), "en", "pt")

    assert [line.text for line in translated] == ["hello", "world"]
    assert [line.start_ms for line in translated] == [0, 1000]
