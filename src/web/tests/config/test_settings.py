from legendarr_web.config.settings import WebSettings, get_web_settings


def test_settings_have_documented_defaults(monkeypatch):
    # conftest.py's session-wide `_isolated_data_dir` fixture points LEGENDARR_DATA_DIR
    # at a temp dir — clear it so the class's own defaults are what's under test.
    monkeypatch.delenv("LEGENDARR_DATA_DIR", raising=False)
    settings = WebSettings()

    assert settings.backend_api_url == "http://127.0.0.1:8000/api"
    assert settings.data_dir.name == "data"


def test_settings_read_env_vars_with_legendarr_prefix(monkeypatch):
    monkeypatch.setenv("LEGENDARR_BACKEND_API_URL", "http://backend:9999/api")

    settings = WebSettings()

    assert settings.backend_api_url == "http://backend:9999/api"


def test_get_web_settings_is_cached(monkeypatch):
    # `lru_cache` is process-wide: another test may already have populated it, so
    # clear the cache around this test to guarantee the first call here is uncached.
    get_web_settings.cache_clear()
    try:
        monkeypatch.setenv("LEGENDARR_BACKEND_API_URL", "http://backend:9999/api")

        first = get_web_settings()
        monkeypatch.setenv("LEGENDARR_BACKEND_API_URL", "http://other:1/api")

        assert get_web_settings() is first
        assert first.backend_api_url == "http://backend:9999/api"
    finally:
        get_web_settings.cache_clear()
