import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_proxies_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def test_subtitle_proxies_page_lists_none_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_proxies_handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-proxies/")

    assert response.status_code == 200
    assert "Add Proxy" in response.text


def test_page_renders_registered_proxy_cards(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "FlareSolverr",
                    "host": "http://10.0.1.1:8191/",
                    "enabled": True,
                }
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-proxies/")

    assert response.status_code == 200
    body = response.text
    assert "FlareSolverr" in body
    assert "http://10.0.1.1:8191/" in body
    assert 'role="switch"' in body
    assert "/settings/subtitle-proxies/1/edit" in body


def test_count_badge_reflects_registered_proxies(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1, "name": "FlareSolverr"}])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-proxies/count")

    assert response.status_code == 200
    assert ">1<" in response.text


def test_count_badge_hidden_when_no_proxies(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_proxies_handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-proxies/count")

    assert response.status_code == 200
    assert "hidden" in response.text
    assert "app-nav-badge" not in response.text


def test_create_subtitle_proxy_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/subtitle-proxies/":
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-proxies/",
            data={"name": "FlareSolverr", "host": "http://10.0.1.1:8191/"},
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-proxies/"
    assert "toast=FlareSolverr+added." in str(response.request.url)
    assert "toast_type=success" in str(response.request.url)


def test_create_subtitle_proxy_rerenders_form_when_unreachable(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/subtitle-proxies/":
            return httpx.Response(422, json={"detail": "Could not connect to the proxy"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-proxies/",
            data={"name": "FlareSolverr", "host": "http://10.0.1.1:8191/"},
        )

    assert response.status_code == 422
    assert "Could not connect to the proxy" in response.text
    assert 'name="host"' in response.text  # the form is shown again, not a redirect
    assert 'data-toast-type="error"' in response.text


def test_test_subtitle_proxy_route_is_not_shadowed_by_proxy_id_route(stub_backend_client):
    """`POST /test` must be matched before the `POST /{proxy_id}` update route, or the
    literal "test" segment gets swallowed as a `proxy_id` path parameter."""
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/subtitle-proxies/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-proxies/test",
            data={"name": "FlareSolverr", "host": "http://10.0.1.1:8191/"},
        )

    assert response.status_code == 200
    assert 'data-toast-message="Connection successful"' in response.text
    assert 'data-toast-type="success"' in response.text


def test_update_subtitle_proxy_redirects_with_success_toast(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT" and request.url.path == "/subtitle-proxies/1":
            return httpx.Response(200, json={"id": 1, "name": "FlareSolverr"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-proxies/1",
            data={"name": "FlareSolverr", "host": "http://10.0.1.2:8191/"},
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-proxies/"
    assert "toast=FlareSolverr+updated." in str(response.request.url)


def test_edit_missing_proxy_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/subtitle-proxies/1":
            return httpx.Response(404, json={"detail": "Subtitle proxy not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/subtitle-proxies/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-proxies/"


def test_delete_missing_proxy_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE" and request.url.path == "/subtitle-proxies/1":
            return httpx.Response(404, json={"detail": "Subtitle proxy not found"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/subtitle-proxies/1/delete")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/subtitle-proxies/"


def test_create_shows_error_on_duplicate_name(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/subtitle-proxies/":
            return httpx.Response(409, json={"detail": "A proxy with this name already exists"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/subtitle-proxies/",
            data={"name": "FlareSolverr", "host": "http://10.0.1.1:8191/"},
        )

    assert response.status_code == 409
    assert "A proxy with this name already exists" in response.text


def test_toggle_enabled_reverts_switch_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post("/settings/subtitle-proxies/1/enabled", data={"enabled": "false"})

    assert response.status_code == 200
    assert 'role="switch"' in response.text
    assert "checked" in response.text
