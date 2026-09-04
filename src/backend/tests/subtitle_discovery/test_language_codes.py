from legendarr_backend.subtitle_discovery.language_codes import (
    display_language_code,
    normalize_language_code,
)


def test_normalize_leaves_iso_639_1_code_unchanged():
    assert normalize_language_code("en") == "en"


def test_normalize_maps_iso_639_2_code_to_iso_639_1():
    assert normalize_language_code("eng") == "en"
    assert normalize_language_code("por") == "pt"


def test_normalize_drops_region_subtag():
    assert normalize_language_code("pt-BR") == "pt"


def test_normalize_is_case_insensitive():
    assert normalize_language_code("ENG") == "en"


def test_normalize_falls_back_to_lowercased_primary_subtag_when_unmapped():
    assert normalize_language_code("und") == "und"


def test_display_keeps_region_subtag():
    assert display_language_code("pt-BR") == "pt-br"


def test_display_maps_iso_639_2_code_without_a_region_subtag():
    assert display_language_code("por") == "pt"
    assert display_language_code("eng") == "en"


def test_display_is_case_insensitive():
    assert display_language_code("PT-BR") == "pt-br"


def test_display_falls_back_to_lowercased_primary_subtag_when_unmapped():
    assert display_language_code("und") == "und"
