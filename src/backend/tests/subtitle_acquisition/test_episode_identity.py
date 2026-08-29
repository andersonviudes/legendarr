from legendarr_backend.subtitle_acquisition.candidate_evaluation.episode_identity import (
    passes_episode_identity,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


def _result(release_name: str, **kwargs) -> SubtitleSearchResult:
    return SubtitleSearchResult(release_name=release_name, download_id="1", language="en", **kwargs)


def test_passes_a_movie_search_with_no_season_or_episode():
    assert passes_episode_identity(_result("Movie.Name.2024.WEB-DL"), None, None) is True


def test_passes_a_candidate_with_no_detected_episode():
    assert passes_episode_identity(_result("Show.Name.WEB-DL"), 1, 2) is True


def test_passes_a_candidate_naming_the_matching_episode():
    assert passes_episode_identity(_result("Show.Name.S01E02.WEB-DL"), 1, 2) is True


def test_rejects_a_candidate_naming_a_different_episode():
    assert passes_episode_identity(_result("Show.Name.S01E03.WEB-DL"), 1, 2) is False


def test_rejects_a_candidate_naming_a_different_season():
    assert passes_episode_identity(_result("Show.Name.S02E02.WEB-DL"), 1, 2) is False


def test_a_hash_matched_candidate_bypasses_the_gate():
    candidate = _result("Show.Name.S01E03.WEB-DL", hash_matched=True)

    assert passes_episode_identity(candidate, 1, 2) is True
