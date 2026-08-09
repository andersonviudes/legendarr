import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_providers_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _provider(**overrides) -> dict:
    data = {
        "id": 1,
        "kind": "tvdb",
        "enabled": True,
        "is_configured": True,
    }
    data.update(overrides)
    return data


def test_metadata_providers_page_lists_none_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_providers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/")

    assert response.status_code == 200
    assert "Metadata source" in response.text
    assert 'aria-current="page"' in response.text


def test_page_renders_provider_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _provider(id=1, kind="tvdb", enabled=True),
                _provider(id=2, kind="imdb", enabled=False),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/")

    assert response.status_code == 200
    body = response.text
    assert "TheTVDB" in body
    assert "IMDb" in body
    assert 'role="switch"' in body
    assert "/settings/metadata-source/1/edit" in body


def test_page_hides_toggle_for_unconfigured_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_provider(id=1, kind="tvdb", is_configured=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/")

    assert response.status_code == 200
    assert 'role="switch"' not in response.text
    assert "Not configured" in response.text


def test_count_badge_reflects_enabled_providers(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_provider(id=1, enabled=True), _provider(id=2, enabled=False)]
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/count")

    assert response.status_code == 200
    assert ">1<" in response.text


def test_count_badge_hidden_when_none_enabled(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_providers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/count")

    assert response.status_code == 200
    assert "hidden" in response.text
    assert "app-nav-badge" not in response.text


def test_edit_form_does_not_prefill_api_key(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_provider(id=1, kind="tvdb"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/1/edit")

    assert 'value=""' in response.text or "value=''" in response.text


def test_update_provider_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/metadata-providers/1":
            return httpx.Response(200, json=_provider(id=1, kind="tvdb"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/metadata-source/1", data={"kind": "tvdb", "api_key": "a-key"}
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/metadata-source/"
    assert "toast=TheTVDB+updated." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_update_provider_rerenders_form_on_validation_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/metadata-providers/1":
            return httpx.Response(422, json={"detail": "api_key is required"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/metadata-source/1", data={"kind": "tvdb", "api_key": ""})

    assert response.status_code == 422
    assert "api_key is required" in response.text
    assert 'name="api_key"' in response.text  # the form is shown again, not a redirect


def test_toggle_enabled_reverts_switch_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/metadata-source/1/enabled", data={"enabled": "false"})

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "checked" in response.text


def test_edit_missing_provider_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/metadata-providers/1":
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/metadata-source/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/metadata-source/"


def test_test_connection_shows_message(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/metadata-providers/1/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/metadata-source/1/test", data={"kind": "tvdb", "api_key": "a-key"}
        )

    assert response.status_code == 200
    assert "Connection successful" in response.text
