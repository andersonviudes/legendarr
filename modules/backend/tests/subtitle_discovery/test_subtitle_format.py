from legendarr_backend.subtitle_discovery.subtitle_format import (
    SubtitleLine,
    compose_srt,
    parse_srt,
)

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:01,500
hello

2
00:00:01,500 --> 00:00:03,000
world
line2

"""


def test_parse_srt_preserves_index_and_timing():
    lines = parse_srt(SAMPLE_SRT)

    assert lines == [
        SubtitleLine(index=1, start_ms=0, end_ms=1500, text="hello"),
        SubtitleLine(index=2, start_ms=1500, end_ms=3000, text="world\nline2"),
    ]


def test_compose_srt_round_trips_parse_srt():
    lines = parse_srt(SAMPLE_SRT)

    assert parse_srt(compose_srt(lines)) == lines
