from legendarr_backend.subtitle_discovery.strip_subtitle_style_tags import (
    strip_subtitle_style_tags,
)


def test_strips_tags_from_an_srt_file_in_place(tmp_path):
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text(
        '1\n00:00:00,000 --> 00:00:01,000\n<font color="yellow">{\\an8}Hi</font>\n\n',
        encoding="utf-8",
    )

    result = strip_subtitle_style_tags(subtitle_path)

    assert result is True
    assert "Hi" in subtitle_path.read_text(encoding="utf-8")
    assert "<font" not in subtitle_path.read_text(encoding="utf-8")
    assert "{\\an8}" not in subtitle_path.read_text(encoding="utf-8")


def test_returns_false_and_leaves_the_file_untouched_for_an_unsupported_format(tmp_path):
    subtitle_path = tmp_path / "movie.ass"
    subtitle_path.write_text("[Script Info]\noriginal", encoding="utf-8")

    result = strip_subtitle_style_tags(subtitle_path)

    assert result is False
    assert subtitle_path.read_text(encoding="utf-8") == "[Script Info]\noriginal"
