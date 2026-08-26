import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_servers_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def _server(**overrides) -> dict:
    data = {
        "id": 1,
        "kind": "plex",
        "enabled": True,
        "base_url": "http://plex.local:32400",
        "is_configured": True,
    }
    data.update(overrides)
    return data


def test_media_servers_page_lists_none_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_servers_handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/")

    assert response.status_code == 200
    assert "Media servers" in response.text
    assert 'aria-current="page"' in response.text


def test_page_renders_server_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _server(id=1, kind="plex", enabled=True),
                _server(id=2, kind="jellyfin", enabled=False),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/")

    assert response.status_code == 200
    body = response.text
    assert "Plex" in body
    assert "Jellyfin" in body
    assert 'role="switch"' in body
    assert "/settings/media-servers/1/edit" in body


def test_page_hides_toggle_for_unconfigured_server(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_server(id=1, kind="plex", is_configured=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/")

    assert response.status_code == 200
    assert 'role="switch"' not in response.text
    assert "Not configured" in response.text


def test_count_badge_reflects_enabled_servers(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_server(id=1, enabled=True), _server(id=2, enabled=False)])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/count")

    assert response.status_code == 200
    assert ">1<" in response.text


def test_edit_form_prefills_base_url_but_not_token(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_server(id=1, kind="plex", base_url="http://plex.local"))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/1/edit")

    assert 'value="http://plex.local"' in response.text
    assert 'value=""' in response.text or "value=''" in response.text


def test_update_server_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/media-servers/1":
            return httpx.Response(200, json=_server(id=1, kind="plex"))
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/media-servers/1",
            data={"kind": "plex", "base_url": "http://plex.local:32400", "token": "tok"},
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/media-servers/"
    assert "toast=Plex+updated." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_update_server_rerenders_form_on_validation_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path == "/media-servers/1":
            return httpx.Response(422, json={"detail": "base_url is required"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/media-servers/1", data={"kind": "plex", "base_url": "", "token": ""}
        )

    assert response.status_code == 422
    assert "base_url is required" in response.text
    assert 'name="base_url"' in response.text  # the form is shown again, not a redirect


def test_toggle_enabled_reverts_switch_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/media-servers/1/enabled", data={"enabled": "false"})

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "checked" in response.text


def test_edit_missing_server_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/media-servers/1":
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/media-servers/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/media-servers/"


def test_test_connection_shows_message(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/media-servers/1/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/media-servers/1/test",
            data={"kind": "plex", "base_url": "http://plex.local:32400", "token": "tok"},
        )

    assert response.status_code == 200
    assert "Connection successful" in response.text
