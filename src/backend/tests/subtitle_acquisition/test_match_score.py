from legendarr_backend.subtitle_acquisition.match_score import pick_best_match, score_candidate
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


def _result(release_name: str) -> SubtitleSearchResult:
    return SubtitleSearchResult(release_name=release_name, download_id="1", language="en")


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
