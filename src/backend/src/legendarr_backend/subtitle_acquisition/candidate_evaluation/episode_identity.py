"""Season/episode identity gate — a candidate whose release name detectably names a
different episode than the one being searched for is rejected outright, not merely
scored lower. `match_score.py`'s `ATTRIBUTE_WEIGHTS` deliberately has no season/episode
entry: a near-miss title (`S01E02` vs `S01E03`) scores too close on `SequenceMatcher`
alone for any additive weight to reliably outweigh it, so this runs as a hard pre-filter
instead — the same shape `release_filters.py`'s must-contain/must-not-contain check
already uses.
"""

from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_attributes import (
    extract_release_attributes,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


def passes_episode_identity(
    candidate: SubtitleSearchResult, season_number: int | None, episode_number: int | None
) -> bool:
    """`False` only when `candidate.release_name` detectably names a season/episode that
    conflicts with `season_number`/`episode_number` — the ground truth already resolved
    from Sonarr (`SubtitleSearchContext.season_number`/`.episode_number`), not another
    regex read of the reference filename. `True` for a movie search (both `None`), a
    candidate with no detected season/episode (nothing to compare — same tolerance
    `match_score.ATTRIBUTE_WEIGHTS` already uses), or a hash-verified candidate
    (`candidate.hash_matched`) — its content hash already guarantees file identity more
    strongly than any filename text could, so a mislabeled-but-hash-correct release name
    isn't rejected on a technicality.
    """
    if candidate.hash_matched:
        return True
    if season_number is None and episode_number is None:
        return True
    attributes = extract_release_attributes(candidate.release_name)
    if attributes.season is not None and attributes.season != season_number:
        return False
    if attributes.episode is not None and attributes.episode != episode_number:
        return False
    return True
