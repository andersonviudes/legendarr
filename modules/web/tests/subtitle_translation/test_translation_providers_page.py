import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_providers_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/settings/translation-defaults":
        return httpx.Response(200, json={"default_translation_provider": None})
    return httpx.Response(200, json=[])


def _provider(**overrides) -> dict:
    data = {
        "id": 1,
        "kind": "deepl",
        "enabled": True,
        "endpoint": None,
        "is_configured": True,
    }
    data.update(overrides)
    return data


def test_translation_providers_page_lists_none_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_providers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/")

    assert response.status_code == 200
    assert "Providers" in response.text
    assert 'aria-current="page"' in response.text


def test_page_renders_provider_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(
            200,
            json=[
                _provider(id=1, kind="deepl", enabled=True),
                _provider(id=2, kind="libretranslate", enabled=False),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/")

    assert response.status_code == 200
    body = response.text
    assert "DeepL" in body
    assert "LibreTranslate" in body
    assert 'role="switch"' in body
    assert "Requires credentials" in body
    assert "/settings/translation-providers/1/edit" in body


def test_page_hides_toggle_for_unconfigured_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(200, json=[_provider(id=1, kind="deepl", is_configured=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/")

    assert response.status_code == 200
    assert 'role="switch"' not in response.text
    assert "Not configured" in response.text


def test_edit_form_shows_api_key_for_deepl(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_provider(id=1, kind="deepl"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/1/edit")

    assert response.status_code == 200
    assert 'name="api_key"' in response.text
    assert 'name="endpoint"' not in response.text
    assert "data-test-connection" in response.text


def test_edit_form_shows_endpoint_and_api_key_for_libretranslate(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_provider(id=1, kind="libretranslate", endpoint="http://localhost:5000"),
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/1/edit")

    assert response.status_code == 200
    assert 'name="endpoint"' in response.text
    assert 'value="http://localhost:5000"' in response.text
    assert 'name="api_key"' in response.text


def test_edit_form_does_not_prefill_api_key(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_provider(id=1, kind="deepl"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/1/edit")

    assert 'value=""' in response.text or "value=''" in response.text


def test_update_provider_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/translation-providers/1":
            return httpx.Response(200, json=_provider(id=1, kind="deepl"))
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/translation-providers/1", data={"kind": "deepl", "api_key": "a-key"}
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/translation-providers/"
    assert "toast=DeepL+updated." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_update_provider_rerenders_form_on_validation_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/translation-providers/1":
            return httpx.Response(422, json={"detail": "api_key is required"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/translation-providers/1", data={"kind": "deepl", "api_key": ""}
        )

    assert response.status_code == 422
    assert "api_key is required" in response.text
    assert 'name="api_key"' in response.text  # the form is shown again, not a redirect


def test_toggle_enabled_reverts_switch_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/translation-providers/1/enabled", data={"enabled": "false"}
        )

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "checked" in response.text


def test_edit_missing_provider_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/translation-providers/1":
            return httpx.Response(404, json={"detail": "not found"})
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/translation-providers/"


def test_page_shows_default_badge_and_hides_its_own_set_default_button(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": "deepl"})
        return httpx.Response(
            200,
            json=[
                _provider(id=1, kind="deepl", enabled=True),
                _provider(id=2, kind="libretranslate", enabled=False),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/")

    assert response.status_code == 200
    body = response.text
    assert "Default" in body
    assert "/settings/translation-providers/1/default" not in body
    assert "/settings/translation-providers/2/default" in body


def test_page_hides_set_default_button_for_unconfigured_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(200, json=[_provider(id=1, kind="deepl", is_configured=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/translation-providers/")

    assert response.status_code == 200
    assert "Set as default" not in response.text


def test_set_default_rerenders_grid_with_new_default(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT" and request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": "libretranslate"})
        if request.url.path == "/translation-providers/2":
            return httpx.Response(200, json=_provider(id=2, kind="libretranslate"))
        return httpx.Response(
            200,
            json=[
                _provider(id=1, kind="deepl", enabled=True),
                _provider(id=2, kind="libretranslate", enabled=True),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/translation-providers/2/default")

    assert response.status_code == 200
    body = response.text
    assert "Default" in body
    assert "/settings/translation-providers/2/default" not in body
    assert "/settings/translation-providers/1/default" in body


def test_set_default_missing_provider_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/translation-providers/1":
            return httpx.Response(404, json={"detail": "not found"})
        if request.url.path == "/settings/translation-defaults":
            return httpx.Response(200, json={"default_translation_provider": None})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/translation-providers/1/default")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/translation-providers/"


def test_test_connection_shows_message(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/translation-providers/1/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/translation-providers/1/test",
            data={"kind": "deepl", "api_key": "a-key"},
        )

    assert response.status_code == 200
    assert "Connection successful" in response.text
