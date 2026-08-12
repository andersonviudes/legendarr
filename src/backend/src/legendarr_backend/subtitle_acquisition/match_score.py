"""Basic match score/cutoff for picking a search result to download — ROADMAP 0.6.0's
"basic match score/cutoff per language profile"; full per-attribute weighting (release
group, resolution, codec, source, edition) is 0.12.0 work.
"""

from difflib import SequenceMatcher

from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

DEFAULT_CUTOFF = 0.4


def pick_best_match(
    candidates: list[SubtitleSearchResult],
    reference_filename: str,
    cutoff: float = DEFAULT_CUTOFF,
) -> SubtitleSearchResult | None:
    """The candidate whose `release_name` is textually closest to `reference_filename`
    (typically the local video's own filename or stem — callers decide), or `None` if
    nothing clears `cutoff`, including when `candidates` is empty.

    Comparison is case-insensitive and ignores `.`/`_`/`-` so a release name like
    "Movie.Name.2024.WEB-DL" scores against a local "Movie Name (2024) WEBDL" file the
    same as it would against another dotted release name.
    """
    if not candidates:
        return None
    reference = _normalize(reference_filename)
    best_candidate = None
    best_score = cutoff
    for candidate in candidates:
        score = SequenceMatcher(None, reference, _normalize(candidate.release_name)).ratio()
        if score >= best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate


def _normalize(value: str) -> str:
    normalized = value.lower()
    for separator in (".", "_", "-", "(", ")"):
        normalized = normalized.replace(separator, " ")
    return " ".join(normalized.split())
