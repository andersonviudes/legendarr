import pytest
from legendarr_backend.config.settings import Settings
from legendarr_backend.subtitle_translation import plugins
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig


class _FixturePlugin:
    """A minimal, correctly-shaped plugin used only by these tests. The "package" these
    tests point `Settings.translation_plugin_packages` at is this test module's own
    `__name__` — `importlib.import_module` just re-fetches the already-imported test
    module, no separate fixture package on `sys.path` needed.
    """

    kind = "fixture-plugin"
    label = "Fixture Plugin"
    name = "fixture-plugin"
    credential_fields = ("api_key",)
    required_credential_fields = ("api_key",)
    plugin_api_version = plugins.SUPPORTED_PLUGIN_API_VERSION

    def __init__(self, config: TranslationProviderConfig) -> None:
        self._config = config

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        return texts


class _WrongVersionPlugin(_FixturePlugin):
    kind = "wrong-version-plugin"
    label = "Wrong Version Plugin"
    plugin_api_version = plugins.SUPPORTED_PLUGIN_API_VERSION + 1


class _MissingAttrPlugin:
    """No `kind`/`label`/`credential_fields`/`required_credential_fields`/`plugin_api_version`."""


class _BuiltinCollisionPlugin(_FixturePlugin):
    kind = "deepl"


@pytest.fixture(autouse=True)
def _clear_plugin_cache():
    """`load_plugin_providers` is `@lru_cache`d for the process lifetime (real
    `Settings.translation_plugin_packages` is env-var-only, so it can't change without a
    restart) — tests need a clean slate before and after each one."""
    plugins.load_plugin_providers.cache_clear()
    yield
    plugins.load_plugin_providers.cache_clear()


def _settings_with(packages: str) -> Settings:
    return Settings(translation_plugin_packages=packages)


def test_loads_a_well_formed_plugin(monkeypatch):
    monkeypatch.setattr(
        plugins, "get_settings", lambda: _settings_with(f"{__name__}:_FixturePlugin")
    )

    registry = plugins.load_plugin_providers()

    assert registry == {"fixture-plugin": _FixturePlugin}


def test_plugin_metadata_helpers_read_from_the_registry(monkeypatch):
    monkeypatch.setattr(
        plugins, "get_settings", lambda: _settings_with(f"{__name__}:_FixturePlugin")
    )

    assert plugins.plugin_kinds() == ("fixture-plugin",)
    assert plugins.plugin_label("fixture-plugin") == "Fixture Plugin"
    assert plugins.plugin_credential_fields("fixture-plugin") == ("api_key",)
    assert plugins.plugin_required_credential_fields("fixture-plugin") == ("api_key",)
    assert plugins.plugin_label("no-such-kind") is None
    assert plugins.plugin_credential_fields("no-such-kind") == ()


def test_skips_malformed_entry(monkeypatch):
    monkeypatch.setattr(plugins, "get_settings", lambda: _settings_with("not-a-valid-entry"))

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_unimportable_module(monkeypatch):
    monkeypatch.setattr(plugins, "get_settings", lambda: _settings_with("no.such.module:Foo"))

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_unknown_class_name(monkeypatch):
    monkeypatch.setattr(plugins, "get_settings", lambda: _settings_with(f"{__name__}:NoSuchClass"))

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_class_missing_required_attrs(monkeypatch):
    monkeypatch.setattr(
        plugins, "get_settings", lambda: _settings_with(f"{__name__}:_MissingAttrPlugin")
    )

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_plugin_api_version_mismatch(monkeypatch):
    monkeypatch.setattr(
        plugins, "get_settings", lambda: _settings_with(f"{__name__}:_WrongVersionPlugin")
    )

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_kind_colliding_with_a_builtin_provider(monkeypatch):
    monkeypatch.setattr(
        plugins, "get_settings", lambda: _settings_with(f"{__name__}:_BuiltinCollisionPlugin")
    )

    registry = plugins.load_plugin_providers()

    assert registry == {}


def test_skips_kind_colliding_with_another_plugin(monkeypatch):
    monkeypatch.setattr(
        plugins,
        "get_settings",
        lambda: _settings_with(f"{__name__}:_FixturePlugin,{__name__}:_FixturePlugin"),
    )

    registry = plugins.load_plugin_providers()

    assert list(registry) == ["fixture-plugin"]


def test_a_broken_entry_does_not_prevent_a_good_one_from_loading(monkeypatch):
    monkeypatch.setattr(
        plugins,
        "get_settings",
        lambda: _settings_with(f"bad.module:Nope,{__name__}:_FixturePlugin"),
    )

    registry = plugins.load_plugin_providers()

    assert list(registry) == ["fixture-plugin"]
