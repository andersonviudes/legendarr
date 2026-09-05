from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    DEFAULT_CUTOFF,
    evaluate_candidate,
    pick_best_match,
    score_candidate,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


def _result(release_name: str, **kwargs) -> SubtitleSearchResult:
    return SubtitleSearchResult(release_name=release_name, download_id="1", language="en", **kwargs)


def test_pick_best_match_returns_none_for_no_candidates():
    assert pick_best_match([], "Movie.Name.2024.WEB-DL.mkv") is None


def test_pick_best_match_returns_none_when_nothing_clears_the_cutoff():
    candidates = [_result("Completely.Unrelated.Release")]

    assert pick_best_match(candidates, "Movie.Name.2024.WEB-DL.mkv") is None


def test_pick_best_match_returns_the_closest_release_name():
    candidates = [
        _result("Some.Other.Movie.2019.BluRay"),
        _result("Movie.Name.2024.WEB-DL.x264-GROUP"),
    ]

    result = pick_best_match(candidates, "Movie.Name.2024.WEB-DL.x264-GROUP.mkv")

    assert result is not None
    assert result.release_name == "Movie.Name.2024.WEB-DL.x264-GROUP"


def test_pick_best_match_ignores_separator_punctuation():
    candidates = [_result("Movie Name (2024) WEBDL")]

    result = pick_best_match(candidates, "Movie.Name.2024.WEBDL.mkv")

    assert result is not None
    assert result.release_name == "Movie Name (2024) WEBDL"


def test_pick_best_match_respects_a_custom_cutoff():
    candidates = [_result("Somewhat.Close.Movie.Name.2024")]

    assert pick_best_match(candidates, "Movie.Name.2024.mkv", cutoff=0.9) is None
    assert pick_best_match(candidates, "Movie.Name.2024.mkv", cutoff=0.3) is not None


def test_score_candidate_scores_an_exact_match_as_one():
    assert score_candidate(_result("Movie.Name.2024.WEB-DL"), "Movie.Name.2024.WEB-DL") == 1.0


def test_score_candidate_scores_an_unrelated_release_low():
    score = score_candidate(_result("Completely.Unrelated.Release"), "Movie.Name.2024.WEB-DL.mkv")

    assert score < 0.4


def test_score_candidate_rewards_matching_attributes_on_top_of_title():
    reference = "Movie.Name.2024.EXTENDED.1080p.WEB-DL.x264-GROUP"

    full_match = score_candidate(_result(reference), reference)
    attribute_mismatch = score_candidate(
        _result("Movie.Name.2024.UNRATED.720p.BluRay.x265-OTHER"), reference
    )

    # Same title on both sides, but every attribute (resolution/source/codec/group/
    # edition) differs — score drops even though the title matched exactly.
    assert attribute_mismatch < full_match
    assert full_match == 1.0


def test_score_candidate_never_lets_attributes_alone_outrank_the_right_title():
    reference = "Movie.Name.2024.1080p.WEB-DL.x264-GROUP"

    wrong_title_same_attributes = score_candidate(
        _result("Completely.Different.Title.1080p.WEB-DL.x264-GROUP"), reference
    )
    right_title_no_attributes = score_candidate(_result("Movie.Name.2024"), reference)

    # A release that shares every attribute tag but is a different title must not
    # outrank one with the right title and no attribute tags at all — attributes only
    # fine-tune the score, they never substitute for the title match.
    assert right_title_no_attributes > wrong_title_same_attributes


def test_score_candidate_ignores_an_attribute_absent_from_the_reference():
    # The reference has no detectable edition, so a candidate's edition (present or
    # not, matching or not) must not affect the score at all.
    reference = "Movie.Name.2024.1080p.WEB-DL.x264-GROUP"

    no_edition = score_candidate(_result("Movie.Name.2024.1080p.WEB-DL.x264-GROUP"), reference)
    with_unmatched_edition = score_candidate(
        _result("Movie.Name.2024.EXTENDED.1080p.WEB-DL.x264-GROUP"), reference
    )

    assert no_edition == with_unmatched_edition


def test_evaluate_candidate_hash_match_forces_the_max_score():
    candidate = _result("Completely.Unrelated.Release", hash_matched=True)

    evaluation = evaluate_candidate(candidate, "Movie.Name.2024.WEB-DL.mkv")

    assert evaluation.score == 1.0
    assert evaluation.hash_matched is True


def test_pick_best_match_accepts_a_hash_matched_candidate_above_any_cutoff():
    candidate = _result("Completely.Unrelated.Release", hash_matched=True)

    result = pick_best_match([candidate], "Movie.Name.2024.WEB-DL.mkv", cutoff=0.99)

    assert result is candidate


def test_evaluate_candidate_rewards_matching_hearing_impaired_preference():
    reference = "Movie.Name.2024.1080p.WEB-DL.x264-GROUP"
    matching = evaluate_candidate(
        _result(reference, hearing_impaired=True), reference, hearing_impaired_preference=True
    )
    mismatching = evaluate_candidate(
        _result(reference, hearing_impaired=False), reference, hearing_impaired_preference=True
    )

    assert matching.score > mismatching.score
    assert matching.hearing_impaired_matched is True
    assert mismatching.hearing_impaired_matched is False


def test_evaluate_candidate_ignores_hearing_impaired_when_either_side_is_unknown():
    reference = "Movie.Name.2024.1080p.WEB-DL.x264-GROUP"
    candidate = _result(reference)  # hearing_impaired defaults to None

    without_preference = evaluate_candidate(candidate, reference)
    with_preference_but_unknown_candidate = evaluate_candidate(
        candidate, reference, hearing_impaired_preference=True
    )

    assert without_preference.score == with_preference_but_unknown_candidate.score
    assert with_preference_but_unknown_candidate.hearing_impaired_matched is None


def test_hearing_impaired_weight_still_keeps_attributes_alone_below_default_cutoff():
    reference = "Movie.Name.2024.EXTENDED.1080p.WEB-DL.x264-GROUP"
    # No title portion at all once known tokens are stripped (title_similarity=0
    # exactly against reference's "movie name 2024") — the real worst case the
    # invariant comment in match_score.py describes.
    candidate = _result("EXTENDED.1080p.WEB-DL.x264-GROUP", hearing_impaired=True)

    score = score_candidate(candidate, reference, hearing_impaired_preference=True)

    assert score < DEFAULT_CUTOFF


def test_evaluate_candidate_matches_source_and_codec_spelling_variants():
    # "WEBDL" (no dash) and "x264"/"h.264" are the same source/codec as "WEB-DL" and
    # "h264" — a spelling difference must not read as an attribute mismatch.
    reference = "Movie.Name.2024.WEBDL.x264"
    candidate = _result("Movie.Name.2024.WEB-DL.h.264")

    evaluation = evaluate_candidate(candidate, reference)

    assert evaluation.attribute_matches["source"] is True
    assert evaluation.attribute_matches["codec"] is True


def test_evaluate_candidate_treats_x264_and_h264_as_the_same_codec():
    reference = "Movie.Name.2024.1080p.WEB-DL.h264"
    candidate = _result("Movie.Name.2024.1080p.WEB-DL.x264")

    assert evaluate_candidate(candidate, reference).attribute_matches["codec"] is True


def test_evaluate_candidate_treats_x265_hevc_and_h265_as_the_same_codec():
    reference = "Movie.Name.2024.1080p.WEB-DL.h265"
    x265 = evaluate_candidate(_result("Movie.Name.2024.1080p.WEB-DL.x265"), reference)
    hevc = evaluate_candidate(_result("Movie.Name.2024.1080p.WEB-DL.HEVC"), reference)

    assert x265.attribute_matches["codec"] is True
    assert hevc.attribute_matches["codec"] is True


def test_evaluate_candidate_keeps_the_h264_and_h265_codec_families_distinct():
    reference = "Movie.Name.2024.1080p.WEB-DL.x264"
    candidate = _result("Movie.Name.2024.1080p.WEB-DL.x265")

    assert evaluate_candidate(candidate, reference).attribute_matches["codec"] is False


def test_evaluate_candidate_keeps_avc_distinct_from_the_h264_codec_family():
    reference = "Movie.Name.2024.1080p.WEB-DL.x264"
    candidate = _result("Movie.Name.2024.1080p.WEB-DL.AVC")

    assert evaluate_candidate(candidate, reference).attribute_matches["codec"] is False


def test_score_candidate_ranks_a_real_same_quality_release_above_a_lower_resolution_one():
    # Regression test for the reported ranking bug: a Radarr-style bracket-tagged
    # reference filename used to lose its source/codec/group attribute bonuses
    # entirely (spelling variants + a release group the old `_GROUP_PATTERN` couldn't
    # see past the bracket), leaving the ranking to noisy leftover-text similarity.
    reference = "Toy Story 5 (2026) - [WEBDL-2160p Proper][EAC3 Atmos 5.1][h265]-NorTekst"
    same_quality = _result("Toy.Story.5.2026.2160p.WEB-DL.h265-NorTekst")
    lower_resolution = _result("Toy.Story.5.2026.1080p.AMZN.WEB-DL.H.264-Kydi")

    assert score_candidate(same_quality, reference) > score_candidate(lower_resolution, reference)
