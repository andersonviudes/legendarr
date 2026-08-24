from legendarr_backend.subtitle_discovery.clean_subtitle_text import clean_subtitle_lines
from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine


def _line(text: str) -> SubtitleLine:
    return SubtitleLine(index=1, start_ms=0, end_ms=1000, text=text)


def test_strips_html_tags():
    cleaned = clean_subtitle_lines([_line('<font color="yellow">hello</font>')])

    assert cleaned == [_line("hello")]


def test_strips_ass_brace_tags():
    cleaned = clean_subtitle_lines([_line(r"{\an8}hello")])

    assert cleaned == [_line("hello")]


def test_collapses_repeated_whitespace():
    cleaned = clean_subtitle_lines([_line("hello    world")])

    assert cleaned == [_line("hello world")]


def test_strips_leading_and_trailing_whitespace_per_sub_line():
    cleaned = clean_subtitle_lines([_line("  hello  \n  world  ")])

    assert cleaned == [_line("hello\nworld")]


def test_preserves_index_and_timing():
    line = SubtitleLine(index=3, start_ms=1000, end_ms=2000, text="<i>hi</i>")

    cleaned = clean_subtitle_lines([line])

    assert cleaned == [SubtitleLine(index=3, start_ms=1000, end_ms=2000, text="hi")]


def test_is_idempotent_on_already_clean_text():
    cleaned_once = clean_subtitle_lines([_line("hello world")])
    cleaned_twice = clean_subtitle_lines(cleaned_once)

    assert cleaned_once == cleaned_twice
