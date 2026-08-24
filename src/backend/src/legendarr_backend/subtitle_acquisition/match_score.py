"""Match score/cutoff for picking a search result to download — ROADMAP 0.6.0's basic
text-similarity cutoff, extended by 0.12.0 into per-attribute weighting: `score_candidate`
combines a title-only similarity ratio (release name with resolution/source/codec/
release-group/edition tokens stripped out) with a weighted bonus for each of those
attributes the candidate shares with the reference filename.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.release_attributes import (
    extract_release_attributes,
    strip_known_attribute_tokens,
)

DEFAULT_CUTOFF = 0.4

# Title outweighs the five attributes combined (100 vs. 50 max) so a candidate can
# never clear DEFAULT_CUTOFF on attribute matches alone, with zero title similarity:
# worst case (all 5 attributes match, title_similarity=0) scores 50/150 = 0.33, below
# 0.4. Attributes still meaningfully move the score once the title is a real match —
# they just can't outrank a correct-title candidate against one that merely shares
# resolution/source/codec tags. Not user-configurable: the roadmap bullet only asks
# for the weighting mechanism, not per-weight tuning.
TITLE_WEIGHT = 100
ATTRIBUTE_WEIGHTS = {
    "resolution": 10,
    "source": 10,
    "codec": 10,
    "release_group": 10,
    "edition": 10,
}


@dataclass(frozen=True)
class CandidateEvaluation:
    """The full breakdown behind one `score_candidate` result — ROADMAP 0.12.0's
    structured audit trail. `attribute_matches` has an entry only for an attribute the
    reference filename had a detectable value for (same exclusion `score_candidate`
    itself applies), `True`/`False` for whether the candidate matched it; a key that's
    missing means "nothing to compare", not "didn't match".
    """

    score: float
    title_similarity: float
    attribute_matches: dict[str, bool]


def pick_best_match(
    candidates: list[SubtitleSearchResult],
    reference_filename: str,
    cutoff: float = DEFAULT_CUTOFF,
) -> SubtitleSearchResult | None:
    """The candidate with the highest `score_candidate` weighted score against
    `reference_filename` (typically the local video's own filename or stem — callers
    decide), or `None` if nothing clears `cutoff`, including when `candidates` is
    empty.
    """
    if not candidates:
        return None
    best_candidate = None
    best_score = cutoff
    for candidate in candidates:
        score = score_candidate(candidate, reference_filename)
        if score >= best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate


def score_candidate(candidate: SubtitleSearchResult, reference_filename: str) -> float:
    """The same weighted score `pick_best_match` ranks candidates by, exposed
    standalone so a caller that wants every candidate's score (not just the best one
    above cutoff) — manual search's results list — doesn't reimplement it.

    Title similarity (`SequenceMatcher` over both strings with attribute tokens
    stripped) anchors the match to the right movie/episode; per-attribute weights only
    fine-tune on top of that, and only for an attribute the reference filename
    actually has a detectable value for — nothing to compare an undetectable attribute
    against, so it's excluded from both the raw score and the normalizing total.
    """
    return evaluate_candidate(candidate, reference_filename).score


def evaluate_candidate(
    candidate: SubtitleSearchResult, reference_filename: str
) -> CandidateEvaluation:
    """`score_candidate`'s full breakdown: the weighted score plus the title
    similarity and per-attribute match results it was computed from — what
    `manage_acquired_subtitle.record_acquired_subtitle` persists as an
    `AcquisitionAttempt` for the winning candidate.
    """
    reference_attributes = extract_release_attributes(reference_filename)
    candidate_attributes = extract_release_attributes(candidate.release_name)
    title_similarity = SequenceMatcher(
        None,
        strip_known_attribute_tokens(reference_filename),
        strip_known_attribute_tokens(candidate.release_name),
    ).ratio()

    raw_score = TITLE_WEIGHT * title_similarity
    max_score = TITLE_WEIGHT
    attribute_matches: dict[str, bool] = {}
    for field, weight in ATTRIBUTE_WEIGHTS.items():
        reference_value = getattr(reference_attributes, field)
        if reference_value is None:
            continue
        max_score += weight
        matched = reference_value == getattr(candidate_attributes, field)
        attribute_matches[field] = matched
        if matched:
            raw_score += weight
    return CandidateEvaluation(
        score=raw_score / max_score,
        title_similarity=title_similarity,
        attribute_matches=attribute_matches,
    )
