from legendarr_backend.language_profiles.models import LanguageProfile


def _profile(**overrides) -> LanguageProfile:
    data = {"name": "default", "source_languages": "en", "target_languages": "pt-BR"}
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
