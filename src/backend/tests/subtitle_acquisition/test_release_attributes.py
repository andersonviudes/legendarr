from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_attributes import (
    ReleaseAttributes,
    extract_release_attributes,
    normalize_release_text,
    strip_known_attribute_tokens,
)


def test_extract_release_attributes_finds_every_vocabulary_category():
    attributes = extract_release_attributes("Movie.Name.2024.EXTENDED.1080p.WEB-DL.x264-GROUP")

    assert attributes == ReleaseAttributes(
        resolution="1080p",
        source="web-dl",
        codec="x264",
        release_group="GROUP",
        edition="extended",
    )


def test_extract_release_attributes_returns_none_for_undetected_attributes():
    assert extract_release_attributes("Movie Name 2024") == ReleaseAttributes()


def test_extract_release_attributes_aliases_4k_to_2160p():
    attributes = extract_release_attributes("Movie.Name.2024.4K.BluRay.x265")

    assert attributes.resolution == "2160p"


def test_extract_release_attributes_does_not_mistake_a_source_dash_for_a_group():
    attributes = extract_release_attributes("Movie.Name.2024.1080p.WEB-DL")

    assert attributes.source == "web-dl"
    assert attributes.release_group is None


def test_extract_release_attributes_finds_the_group_trailing_the_last_vocabulary_token():
    attributes = extract_release_attributes("Movie.Name.2024.1080p.WEB-DL.x264-GROUP")

    assert attributes.release_group == "GROUP"


def test_extract_release_attributes_is_case_insensitive():
    attributes = extract_release_attributes("movie.name.2024.1080p.bluray.x264")

    assert attributes.resolution == "1080p"
    assert attributes.source == "bluray"
    assert attributes.codec == "x264"


def test_strip_known_attribute_tokens_leaves_only_the_title():
    stripped = strip_known_attribute_tokens("Movie.Name.2024.1080p.WEB-DL.x264-GROUP")

    assert stripped == "movie name 2024"


def test_strip_known_attribute_tokens_handles_text_with_no_recognized_tokens():
    assert strip_known_attribute_tokens("Movie Name 2024") == "movie name 2024"


def test_normalize_release_text_collapses_separators_and_lowercases():
    assert normalize_release_text("Movie.Name_(2024)-WEBDL") == "movie name 2024 webdl"


def test_extract_release_attributes_finds_season_and_episode():
    attributes = extract_release_attributes("Show.Name.S01E02.720p.WEB-DL")

    assert attributes.season == 1
    assert attributes.episode == 2


def test_extract_release_attributes_returns_none_season_episode_when_not_present():
    attributes = extract_release_attributes("Movie.Name.2024.1080p.WEB-DL")

    assert attributes.season is None
    assert attributes.episode is None


def test_extract_release_attributes_is_case_insensitive_for_season_episode():
    attributes = extract_release_attributes("show.name.s01e02.720p.web-dl")

    assert attributes.season == 1
    assert attributes.episode == 2
