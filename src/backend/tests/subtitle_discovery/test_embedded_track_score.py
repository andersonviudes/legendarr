from datetime import UTC, datetime

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.subtitle_discovery.embedded_track_score import (
    pick_best_embedded_subtitle,
    score_embedded_subtitle,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


def _subtitle(**overrides) -> Subtitle:
    data = {
        "media_file_id": 1,
        "language": "en",
        "origin": SubtitleOrigin.EMBEDDED,
        "relative_path": "Foo.embedded.0.eng.srt",
        "track_index": 0,
        "content_hash": "hash",
        "scanned_at": datetime.now(UTC),
    }
    data.update(overrides)
    return Subtitle(**data)


def _profile(**overrides) -> LanguageProfile:
    data = {
        "name": "default",
        "source_languages": "en",
        "target_languages": "pt-BR",
        "is_default": True,
    }
    data.update(overrides)
    return LanguageProfile(**data)


def test_score_embedded_subtitle_scores_a_full_match_as_one():
    subtitle = _subtitle(forced=True, hearing_impaired=True)
    profile = _profile(forced=True, hearing_impaired=True)

    assert score_embedded_subtitle(subtitle, profile) == 1.0


def test_score_embedded_subtitle_scores_a_full_mismatch_as_zero():
    subtitle = _subtitle(forced=True, hearing_impaired=True)
    profile = _profile(forced=False, hearing_impaired=False)

    assert score_embedded_subtitle(subtitle, profile) == 0.0


def test_score_embedded_subtitle_weighs_forced_and_hearing_impaired_equally():
    subtitle = _subtitle(forced=False, hearing_impaired=True)
    profile = _profile(forced=False, hearing_impaired=False)

    assert score_embedded_subtitle(subtitle, profile) == 0.5


def test_pick_best_embedded_subtitle_returns_none_for_no_candidates():
    assert pick_best_embedded_subtitle([], _profile()) is None


def test_pick_best_embedded_subtitle_picks_the_one_matching_profile_preference():
    profile = _profile(hearing_impaired=True)
    matching = _subtitle(track_index=1, hearing_impaired=True)
    other = _subtitle(track_index=2, hearing_impaired=False)

    assert pick_best_embedded_subtitle([other, matching], profile) is matching


def test_pick_best_embedded_subtitle_breaks_a_tie_with_the_lowest_track_index():
    profile = _profile()
    first = _subtitle(track_index=1)
    second = _subtitle(track_index=5)

    assert pick_best_embedded_subtitle([second, first], profile) is first
