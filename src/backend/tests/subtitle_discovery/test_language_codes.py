from legendarr_backend.subtitle_discovery.language_codes import normalize_language_code


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
