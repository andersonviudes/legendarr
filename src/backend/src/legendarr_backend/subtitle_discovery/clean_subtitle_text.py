"""Text cleanup pass for a subtitle's lines before translation — ROADMAP 0.13.0:
regex-based fixes for stray formatting tags and whitespace so a translation provider
isn't handed raw formatting artifacts alongside the actual dialogue.
"""

import re

from legendarr_backend.subtitle_discovery.subtitle_format import SubtitleLine

# HTML-ish tags (`<i>`, `<font color="...">`, ...) and ASS/SSA-style brace tags
# (`{\an8}`, `{\i1}`, ...) — "stray color/formatting tags" from the roadmap bullet.
_TAG_PATTERN = re.compile(r"<[^>]+>|\{[^}]+\}")
_WHITESPACE_PATTERN = re.compile(r"[ \t]+")


def clean_subtitle_lines(lines: list[SubtitleLine]) -> list[SubtitleLine]:
    """Strip formatting tags and collapse extra whitespace from every line's text,
    preserving index/timing."""
    return [
        SubtitleLine(
            index=line.index,
            start_ms=line.start_ms,
            end_ms=line.end_ms,
            text=_clean_text(line.text),
        )
        for line in lines
    ]


def _clean_text(text: str) -> str:
    text = _TAG_PATTERN.sub("", text)
    return "\n".join(
        _WHITESPACE_PATTERN.sub(" ", sub_line).strip() for sub_line in text.split("\n")
    ).strip()
