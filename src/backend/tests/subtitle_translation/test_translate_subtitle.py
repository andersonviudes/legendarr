from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine
from legendarr_backend.subtitle_translation.providers.echo import EchoTranslationProvider
from legendarr_backend.subtitle_translation.translate_subtitle import translate_subtitle


def test_translate_subtitle_preserves_timing_and_order():
    lines = [
        SubtitleLine(index=1, start_ms=0, end_ms=1000, text="hello"),
        SubtitleLine(index=2, start_ms=1000, end_ms=2000, text="world"),
    ]

    translated = translate_subtitle(lines, EchoTranslationProvider(), "en", "pt")

    assert [line.text for line in translated] == ["hello", "world"]
    assert [line.start_ms for line in translated] == [0, 1000]


def test_translate_subtitle_calls_translate_batch_once_with_every_line():
    lines = [
        SubtitleLine(index=1, start_ms=0, end_ms=1000, text="hello"),
        SubtitleLine(index=2, start_ms=1000, end_ms=2000, text="world"),
    ]
    calls = []

    class _RecordingProvider:
        name = "recording"

        def translate_batch(self, texts, source_language, target_language):
            calls.append((texts, source_language, target_language))
            return [text.upper() for text in texts]

    translated = translate_subtitle(lines, _RecordingProvider(), "en", "pt")

    assert calls == [(["hello", "world"], "en", "pt")]
    assert [line.text for line in translated] == ["HELLO", "WORLD"]
