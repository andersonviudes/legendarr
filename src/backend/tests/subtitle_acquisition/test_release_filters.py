from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_filters import (
    passes_release_name_filters,
)


def test_passes_release_name_filters_with_no_terms_always_passes():
    assert passes_release_name_filters("Movie.Name.2024.WEB-DL", [], []) is True


def test_must_contain_passes_when_at_least_one_term_matches():
    assert (
        passes_release_name_filters("Movie.Name.2024.PROPER.WEB-DL", ["PROPER", "REPACK"], [])
        is True
    )


def test_must_contain_rejects_when_no_term_matches():
    assert passes_release_name_filters("Movie.Name.2024.WEB-DL", ["PROPER", "REPACK"], []) is False


def test_must_contain_is_case_insensitive():
    assert passes_release_name_filters("movie.name.2024.proper", ["PROPER"], []) is True


def test_must_not_contain_rejects_when_any_term_matches():
    assert passes_release_name_filters("Movie.Name.2024.CAM", [], ["CAM", "TS"]) is False


def test_must_not_contain_passes_when_no_term_matches():
    assert passes_release_name_filters("Movie.Name.2024.WEB-DL", [], ["CAM", "TS"]) is True


def test_must_not_contain_is_case_insensitive():
    assert passes_release_name_filters("movie.name.2024.cam", [], ["CAM"]) is False


def test_must_contain_and_must_not_contain_combine():
    assert passes_release_name_filters("Movie.Name.2024.PROPER.CAM", ["PROPER"], ["CAM"]) is False
