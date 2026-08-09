from dataclasses import dataclass
from datetime import timedelta

import srt


@dataclass(frozen=True)
class SubtitleLine:
    index: int
    start_ms: int
    end_ms: int
    text: str


def parse_srt(content: str) -> list[SubtitleLine]:
    """Parse an `.srt` file's contents into translatable lines, preserving timing/order."""
    return [
        SubtitleLine(
            index=subtitle.index,
            start_ms=round(subtitle.start.total_seconds() * 1000),
            end_ms=round(subtitle.end.total_seconds() * 1000),
            text=subtitle.content,
        )
        for subtitle in srt.parse(content)
    ]


def compose_srt(lines: list[SubtitleLine]) -> str:
    """Write translated lines back out as `.srt` file contents, preserving timing/order."""
    return srt.compose(
        [
            srt.Subtitle(
                index=line.index,
                start=timedelta(milliseconds=line.start_ms),
                end=timedelta(milliseconds=line.end_ms),
                content=line.text,
            )
            for line in lines
        ],
        reindex=False,
    )
