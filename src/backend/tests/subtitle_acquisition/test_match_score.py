from legendarr_backend.subtitle_acquisition.match_score import pick_best_match
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
