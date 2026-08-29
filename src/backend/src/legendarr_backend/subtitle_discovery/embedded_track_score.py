"""Score for picking the best of several embedded subtitle tracks in the same language —
the embedded-track counterpart to `subtitle_acquisition.candidate_evaluation.match_score`,
used when `translate_media_file` needs a single automatic pick among rows
`scan_video_subtitles` intentionally keeps all of (ROADMAP 0.11.0's manual source list).

An embedded track has neither a reference filename to compare a title against nor a
verified content-hash concept — it's already the file being scanned, not something matched
against it — so this can't reuse `match_score.py`'s algorithm. It scores on the only two
signals an embedded track actually carries: `forced`/`hearing_impaired` container
disposition flags, weighed against the caller's `LanguageProfile` preference for each. Both
sides are plain, non-nullable `bool`s (unlike `match_score.py`'s `hearing_impaired_preference:
bool | None`), so there's no "nothing to compare" case to special-case here.
"""

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.subtitle_discovery.models import Subtitle

FORCED_WEIGHT = 1
HEARING_IMPAIRED_WEIGHT = 1


def score_embedded_subtitle(subtitle: Subtitle, profile: LanguageProfile) -> float:
    """Weighted match between `subtitle`'s disposition flags and `profile`'s preferences,
    normalized to 0.0-1.0. Forced and hearing-impaired matches count equally — neither
    signal is a stronger identity indicator than the other the way, e.g., a title match is
    in `match_score.py`.
    """
    raw_score = 0
    if subtitle.forced == profile.forced:
        raw_score += FORCED_WEIGHT
    if subtitle.hearing_impaired == profile.hearing_impaired:
        raw_score += HEARING_IMPAIRED_WEIGHT
    return raw_score / (FORCED_WEIGHT + HEARING_IMPAIRED_WEIGHT)


def pick_best_embedded_subtitle(
    subtitles: list[Subtitle], profile: LanguageProfile
) -> Subtitle | None:
    """The highest-`score_embedded_subtitle` subtitle in `subtitles`, or `None` if
    `subtitles` is empty. Ties (including "every track scores the same") are broken by the
    lowest `track_index` — the container's first stream in that language — so the pick stays
    deterministic across scans instead of depending on `scanned_at`/row-fetch order.
    """
    if not subtitles:
        return None
    return max(
        subtitles,
        key=lambda subtitle: (
            score_embedded_subtitle(subtitle, profile),
            -(subtitle.track_index or 0),
        ),
    )
