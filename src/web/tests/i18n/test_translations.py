import json
from pathlib import Path

from legendarr_web import i18n
from legendarr_web.i18n.translator import SUPPORTED_UI_LOCALES, translate

LOCALES_DIR = Path(i18n.__file__).parent / "locales"


def _catalog_keys(locale: str) -> set[str]:
    return set(json.loads((LOCALES_DIR / f"{locale}.json").read_text()))


def test_every_locale_has_the_same_keys_as_english():
    en_keys = _catalog_keys("en")
    for code, _ in SUPPORTED_UI_LOCALES:
        assert _catalog_keys(code) == en_keys, f"{code}.json is out of sync with en.json"


def test_supported_locales_have_a_catalog_file():
    for code, _ in SUPPORTED_UI_LOCALES:
        assert (LOCALES_DIR / f"{code}.json").exists()


def test_translate_falls_back_to_english_for_an_unknown_locale():
    assert translate("fr", "common.save") == translate("en", "common.save")


def test_translate_falls_back_to_the_key_itself_when_missing_everywhere():
    assert translate("en", "totally.made.up.key") == "totally.made.up.key"


def test_translate_interpolates_kwargs():
    assert translate("en", "arr_services.add_server", label="Radarr") == "Add Radarr Server"
