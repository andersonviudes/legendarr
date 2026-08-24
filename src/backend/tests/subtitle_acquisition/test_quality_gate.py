from legendarr_backend.subtitle_acquisition.quality_gate import passes_quality_gate
from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine, compose_srt


def _srt(start_ms: int, end_ms: int, text: str = "hello") -> str:
    return compose_srt([SubtitleLine(index=1, start_ms=start_ms, end_ms=end_ms, text=text)])


def test_passes_quality_gate_accepts_normal_subtitle():
    content = compose_srt(
        [
            SubtitleLine(index=1, start_ms=0, end_ms=1_500, text="hello"),
            SubtitleLine(index=2, start_ms=60_000, end_ms=90_000, text="world"),
        ]
    )

    assert passes_quality_gate(content) is True


def test_rejects_content_below_min_file_size():
    assert passes_quality_gate("1") is False


def test_rejects_unparseable_content():
    assert passes_quality_gate("this is not an srt file, just garbage text" * 2) is False


def test_rejects_span_below_min_duration():
    assert passes_quality_gate(_srt(0, 1_000)) is False


def test_rejects_span_above_max_duration():
    thirteen_hours_ms = 13 * 60 * 60 * 1000
    assert passes_quality_gate(_srt(0, thirteen_hours_ms)) is False


def test_accepts_span_at_min_duration_boundary():
    assert passes_quality_gate(_srt(0, 10_000)) is True
