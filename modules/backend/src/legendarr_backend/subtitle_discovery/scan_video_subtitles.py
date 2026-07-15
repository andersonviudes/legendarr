from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SubtitleOrigin(StrEnum):
    EMBEDDED = "embedded"
    EXTERNAL = "external"


@dataclass(frozen=True)
class DiscoveredSubtitle:
    language: str
    origin: SubtitleOrigin
    source_path: Path
    track_index: int | None = None


def scan_video_subtitles(video_path: Path) -> list[DiscoveredSubtitle]:
    """Discover subtitle tracks for a video file.

    External sibling files (``*.srt``, ``*.ass``) are always considered;
    embedded tracks additionally require probing the container (ffprobe),
    which is wired in as the feature matures.
    """
    subtitles: list[DiscoveredSubtitle] = []
    for sibling in video_path.parent.glob(f"{video_path.stem}*"):
        if sibling.suffix.lower() in {".srt", ".ass", ".ssa", ".vtt"}:
            subtitles.append(
                DiscoveredSubtitle(
                    language=_guess_language_from_filename(sibling),
                    origin=SubtitleOrigin.EXTERNAL,
                    source_path=sibling,
                )
            )
    return subtitles


def _guess_language_from_filename(path: Path) -> str:
    parts = path.stem.split(".")
    return parts[-1].lower() if len(parts) > 1 else "und"
