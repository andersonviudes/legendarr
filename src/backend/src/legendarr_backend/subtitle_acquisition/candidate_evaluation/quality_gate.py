"""Quality-gate validation for a just-downloaded subtitle — ROADMAP 0.13.0's
"obviously broken results rejected" bounds, checked before a candidate is ever
accepted so acquisition can't hand translation (or the user) a truncated or garbage
subtitle just because it cleared the match-score cutoff.
"""

from legendarr_backend.subtitle_discovery.subtitle_format import parse_srt

MIN_FILE_SIZE_BYTES = 32
MIN_CUE_COUNT = 1
MIN_DURATION_MS = 10_000
MAX_DURATION_MS = 12 * 60 * 60 * 1000


def passes_quality_gate(content: str) -> bool:
    """`False` for content that's empty/near-empty, unparseable as `.srt`, has no cues,
    or whose total cue span (last cue's end minus first cue's start) falls outside
    `MIN_DURATION_MS`/`MAX_DURATION_MS` — `True` otherwise. Not a video-relative check:
    there's no probed video runtime to compare against, so this only sanity-checks the
    subtitle's own span.
    """
    if len(content.encode("utf-8")) < MIN_FILE_SIZE_BYTES:
        return False
    try:
        lines = parse_srt(content)
    except Exception:
        return False
    if len(lines) < MIN_CUE_COUNT:
        return False
    span_ms = max(line.end_ms for line in lines) - min(line.start_ms for line in lines)
    return MIN_DURATION_MS <= span_ms <= MAX_DURATION_MS
