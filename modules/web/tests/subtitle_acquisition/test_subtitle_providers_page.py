import json

import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_providers_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _provider(**overrides) -> dict:
    data = {
        "id": 1,
        "kind": "opensubtitles",
        "enabled": True,
        "username": None,
        "is_configured": True,
        "use_hash": True,
        "include_ai_translated": False,
        "include_machine_translated": False,
    }
    data.update(overrides)
    return data


def test_subtitle_providers_page_lists_none_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_providers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/")

    assert response.status_code == 200
    assert "Subtitle Providers" in response.text


def test_page_renders_provider_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _provider(id=1, kind="opensubtitles", enabled=True),
                _provider(id=2, kind="napiprojekt", enabled=False),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/")

    assert response.status_code == 200
    body = response.text
    assert "OpenSubtitles" in body
    assert "Napiprojekt" in body
    assert 'role="switch"' in body
    assert "Requires credentials" in body
    assert "No credentials needed" in body
    assert "/settings/subtitle-providers/1/edit" in body


def test_page_hides_toggle_for_unconfigured_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_provider(id=1, kind="opensubtitles", is_configured=False)]
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/")

    assert response.status_code == 200
    assert 'role="switch"' not in response.text
    assert "Not configured" in response.text


def test_page_shows_toggle_for_configured_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_provider(id=1, kind="opensubtitles", is_configured=True)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/")

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "Not configured" not in response.text


def test_page_hints_test_connection_for_unverified_credential_less_provider(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_provider(id=1, kind="napiprojekt", is_configured=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/")

    assert response.status_code == 200
    assert 'Run "Test connection" to enable' in response.text
    assert "No credentials needed" not in response.text


def test_count_badge_reflects_enabled_providers(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[_provider(id=1, enabled=True), _provider(id=2, enabled=False)],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/count")

    assert response.status_code == 200
    assert ">1<" in response.text


def test_count_badge_hidden_when_none_enabled(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_providers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/count")

    assert response.status_code == 200
    assert "hidden" in response.text
    assert "app-nav-badge" not in response.text


def test_edit_form_shows_credential_fields_for_kind_that_needs_them(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_provider(id=1, kind="opensubtitles"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert 'name="api_key"' in response.text
    assert "data-test-connection" in response.text


def test_edit_form_hides_credential_fields_for_kind_that_needs_none(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_provider(id=1, kind="napiprojekt"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert 'name="api_key"' not in response.text
    assert "data-test-connection" in response.text
    assert "doesn't need any credentials" in response.text


def test_edit_form_shows_search_options_for_opensubtitles(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200, json=_provider(id=1, kind="opensubtitles", include_ai_translated=True)
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert 'name="use_hash"' in response.text
    assert 'name="include_ai_translated"' in response.text
    assert 'name="include_machine_translated"' in response.text
    assert "Use Hash" in response.text
    assert "AI translation service" in response.text
    assert "machine translated by users" in response.text


def test_edit_form_hides_search_options_for_other_kinds(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_provider(id=1, kind="addic7ed"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert 'name="use_hash"' not in response.text


def test_edit_form_does_not_prefill_api_key(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=_provider(id=1, kind="opensubtitles"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert 'value=""' in response.text or "value=''" in response.text


def test_edit_form_shows_registered_proxies_in_a_combo(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/":
            return httpx.Response(200, json=[{"id": 1, "name": "FlareSolverr", "host": "..."}])
        return httpx.Response(200, json=_provider(id=1, kind="addic7ed", proxy_id=1))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert 'name="proxy_id"' in response.text
    assert "FlareSolverr" in response.text
    assert 'value="1" selected' in response.text


def test_update_provider_forwards_proxy_id(stub_backend_client):
    app = create_app()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/subtitle-providers/1":
            captured.update(json.loads(request.content))
            return httpx.Response(200, json=_provider(id=1, kind="addic7ed"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        client.post(
            "/settings/subtitle-providers/1",
            data={"kind": "addic7ed", "username": "user", "password": "pass", "proxy_id": "1"},
        )

    assert captured["proxy_id"] == 1


def test_update_provider_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/subtitle-providers/1":
            return httpx.Response(200, json=_provider(id=1, kind="opensubtitles"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-providers/1", data={"kind": "opensubtitles", "api_key": "a-key"}
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-providers/"
    assert "toast=OpenSubtitles+updated." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_update_provider_forwards_search_options(stub_backend_client):
    app = create_app()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/subtitle-providers/1":
            captured.update(json.loads(request.content))
            return httpx.Response(200, json=_provider(id=1, kind="opensubtitles"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        client.post(
            "/settings/subtitle-providers/1",
            data={"kind": "opensubtitles", "api_key": "a-key", "include_ai_translated": "true"},
        )

    assert captured["use_hash"] is False
    assert captured["include_ai_translated"] is True
    assert captured["include_machine_translated"] is False


def test_update_provider_omits_search_options_for_a_kind_that_has_none(stub_backend_client):
    """Regression test: the search-option checkboxes only render for OpenSubtitles, but an
    unchecked checkbox is indistinguishable from "not rendered" — the payload must omit
    these fields entirely for another kind, or the backend's presence-based merge would
    silently reset them (e.g. an Addic7ed save zeroing OpenSubtitles-only settings)."""
    app = create_app()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/subtitle-providers/2":
            captured.update(json.loads(request.content))
            return httpx.Response(200, json=_provider(id=2, kind="addic7ed"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        client.post(
            "/settings/subtitle-providers/2",
            data={"kind": "addic7ed", "username": "user", "password": "pass"},
        )

    assert "use_hash" not in captured
    assert "include_ai_translated" not in captured
    assert "include_machine_translated" not in captured


def test_update_provider_rerenders_form_on_validation_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/subtitle-providers/1":
            return httpx.Response(422, json={"detail": "api_key is required"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-providers/1", data={"kind": "opensubtitles", "api_key": ""}
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
        response = client.post("/settings/subtitle-providers/1/enabled", data={"enabled": "false"})

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "checked" in response.text


def test_edit_missing_provider_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-providers/1":
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-providers/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-providers/"


def test_test_connection_shows_message(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-providers/1/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-providers/1/test",
            data={"kind": "opensubtitles", "api_key": "a-key"},
        )

    assert response.status_code == 200
    assert "Connection successful" in response.text
