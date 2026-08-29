"""On-demand "Remove style tags" action for an already-discovered subtitle file — the
same HTML/ASS tag-stripping regex `clean_subtitle_text.py` already runs automatically
before translation (ROADMAP 0.13.0), now available as a standalone per-subtitle action
(ROADMAP 0.23.0) for a subtitle that was never translated through this app at all.
"""

from pathlib import Path

from legendarr_backend.subtitle_discovery.clean_subtitle_text import clean_subtitle_lines
from legendarr_backend.subtitle_discovery.subtitle_format import compose_srt, parse_srt

# `subtitle_format.py` only knows how to parse/compose `.srt` — `.ass`/`.ssa`/`.vtt`
# siblings (see `scan_video_subtitles.py`'s discovery glob) use a different cue syntax
# entirely, not just different tags within an SRT cue, so applying this blindly would
# corrupt them rather than clean them.
_SUPPORTED_SUFFIXES = {".srt"}


def strip_subtitle_style_tags(subtitle_path: Path) -> bool:
    """Strip HTML/ASS-style formatting tags from `subtitle_path`'s cues, overwriting it
    in place. Returns `False` (a no-op, not an error) for a format `subtitle_format.py`
    can't parse — same "expected, not exceptional" posture as
    `sync_subtitle_timing`'s unsupported-extension case.
    """
    if subtitle_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        return False
    lines = parse_srt(subtitle_path.read_text(encoding="utf-8"))
    cleaned = clean_subtitle_lines(lines)
    subtitle_path.write_text(compose_srt(cleaned), encoding="utf-8")
    return True
