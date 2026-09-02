from typing import Any

from legendarr_backend.language_profiles.models import LanguageProfile


def _profile(**overrides) -> LanguageProfile:
    data: dict[str, Any] = {
        "name": "default",
        "source_languages": "en",
        "target_languages": "pt-BR",
    }
    data.update(overrides)
    return LanguageProfile(**data)


def test_source_language_list_splits_and_preserves_order():
    profile = _profile(source_languages="en, ja , ko")

    assert profile.source_language_list == ["en", "ja", "ko"]


def test_target_language_list_splits_and_preserves_order():
    profile = _profile(target_languages="pt-BR,es")

    assert profile.target_language_list == ["pt-BR", "es"]


def test_language_lists_drop_empty_entries():
    profile = _profile(source_languages="en,,")

    assert profile.source_language_list == ["en"]


def test_must_contain_terms_splits_and_preserves_order():
    profile = _profile(release_name_must_contain="PROPER, REPACK")

    assert profile.must_contain_terms == ["PROPER", "REPACK"]


def test_must_not_contain_terms_splits_and_preserves_order():
    profile = _profile(release_name_must_not_contain="CAM,TS")

    assert profile.must_not_contain_terms == ["CAM", "TS"]


def test_must_contain_and_must_not_contain_terms_default_to_empty():
    profile = _profile()

    assert profile.must_contain_terms == []
    assert profile.must_not_contain_terms == []


def test_ocr_embedded_subtitles_defaults_to_false():
    profile = _profile()

    assert profile.ocr_embedded_subtitles is False


def test_speech_to_text_fallback_defaults_to_false():
    profile = _profile()

    assert profile.speech_to_text_fallback is False


def test_auto_translate_defaults_to_true():
    profile = _profile()

    assert profile.auto_translate is True


def test_movie_and_series_match_score_default_to_forty():
    profile = _profile()

    assert profile.movie_match_score == 40
    assert profile.series_match_score == 40
