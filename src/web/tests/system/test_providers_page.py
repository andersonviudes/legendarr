import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app

_TRANSLATION_PROVIDERS = [
    {
        "id": 1,
        "kind": "deepl",
        "enabled": True,
        "endpoint": None,
        "model": None,
        "prompt_template": None,
        "is_configured": True,
        "label": "DeepL",
        "credential_fields": ["api_key"],
    },
    {
        "id": 2,
        "kind": "google",
        "enabled": False,
        "endpoint": None,
        "model": None,
        "prompt_template": None,
        "is_configured": False,
        "label": "Google Translate",
        "credential_fields": ["api_key"],
    },
]

_SUBTITLE_PROVIDERS = [
    {
        "id": 1,
        "kind": "opensubtitles",
        "enabled": True,
        "username": "user",
        "is_configured": True,
        "credentials_required": True,
        "proxy_id": None,
        "use_hash": True,
        "include_ai_translated": False,
        "include_machine_translated": False,
    },
]

_PROVIDER_HEALTH = [
    {
        "kind": "deepl",
        "category": "translation",
        "circuit_open": False,
        "consecutive_failures": 0,
        "opened_at": None,
        "last_success_at": "2026-08-30T10:00:00+00:00",
    },
    {
        "kind": "google",
        "category": "translation",
        "circuit_open": False,
        "consecutive_failures": 0,
        "opened_at": None,
        "last_success_at": None,
    },
    {
        "kind": "opensubtitles",
        "category": "acquisition",
        "circuit_open": True,
        "consecutive_failures": 3,
        "opened_at": "2026-08-30T09:00:00+00:00",
        "last_success_at": None,
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/providers":
        return httpx.Response(200, json=_PROVIDER_HEALTH)
    if request.url.path == "/translation-providers/":
        return httpx.Response(200, json=_TRANSLATION_PROVIDERS)
    if request.url.path == "/subtitle-providers/":
        return httpx.Response(200, json=_SUBTITLE_PROVIDERS)
    return httpx.Response(200, json=[])


def _empty_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/system/providers":
        return httpx.Response(200, json=[])
    if request.url.path in ("/translation-providers/", "/subtitle-providers/"):
        return httpx.Response(200, json=[])
    return httpx.Response(200, json=[])


def test_providers_page_merges_config_and_health(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/system/providers/")

    assert response.status_code == 200
    assert "DeepL" in response.text
    assert "Closed" in response.text
    assert "OpenSubtitles" in response.text
    assert "Open" in response.text


def test_providers_page_shows_not_configured_for_an_unconfigured_provider(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_handler)

    with TestClient(app) as client:
        response = client.get("/system/providers/")

    assert response.status_code == 200
    assert "Not configured" in response.text


def test_providers_page_shows_empty_state_with_no_providers(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_handler)

    with TestClient(app) as client:
        response = client.get("/system/providers/")

    assert response.status_code == 200
    assert "No providers found." in response.text


def test_sidebar_links_to_the_providers_page(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_handler)

    with TestClient(app) as client:
        response = client.get("/system/")

    assert response.status_code == 200
    assert 'href="/system/providers/"' in response.text
