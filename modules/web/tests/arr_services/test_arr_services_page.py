import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _empty_services_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


def test_arr_services_page_lists_no_servers_by_default(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_services_handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/")

    assert response.status_code == 200
    assert "Add Radarr Server" in response.text
    assert "Add Sonarr Server" in response.text


def test_count_badge_reflects_registered_services(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1, "service_type": "radarr"}])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/count")

    assert response.status_code == 200
    assert ">1<" in response.text


def test_count_badge_hidden_when_no_services(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_services_handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/count")

    assert response.status_code == 200
    assert "hidden" in response.text
    assert "app-nav-badge" not in response.text


def test_new_arr_service_form_prefills_default_port(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_empty_services_handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/new", params={"service_type": "sonarr"})

    assert response.status_code == 200
    assert 'value="8989"' in response.text


def test_create_arr_service_redirects_to_list(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/arr-services/":
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/arr-services/",
            data={
                "service_type": "radarr",
                "name": "radarr",
                "host": "radarr",
                "port": 7878,
                "api_key": "api-key",
            },
        )

    assert response.status_code == 200
    assert response.request.url.path == "/settings/arr-services/"


def test_create_arr_service_rerenders_form_when_server_unreachable(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/arr-services/":
            return httpx.Response(422, json={"detail": "Could not connect to the radarr server"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/arr-services/",
            data={
                "service_type": "radarr",
                "name": "radarr",
                "host": "radarr",
                "port": 7878,
                "api_key": "api-key",
            },
        )

    assert response.status_code == 422
    assert "Could not connect to the radarr server" in response.text
    assert 'name="host"' in response.text  # the form is shown again, not a redirect


def test_test_arr_service_route_is_not_shadowed_by_service_id_route(stub_backend_client):
    """`POST /test` must be matched before the `POST /{service_id}` update route, or the
    literal "test" segment gets swallowed as a `service_id` path parameter."""
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/arr-services/test":
            return httpx.Response(200, json={"success": True, "message": "Connection successful"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/arr-services/test",
            data={
                "service_type": "radarr",
                "name": "radarr",
                "host": "radarr",
                "port": 7878,
                "api_key": "api-key",
            },
        )

    assert response.status_code == 200
    assert "Connection successful" in response.text


def _missing_service_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/arr-services/1":
        return httpx.Response(404, json={"detail": "Arr service not found"})
    return httpx.Response(200, json=[])


def test_edit_form_does_not_prefill_api_key(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/arr-services/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "radarr",
                    "service_type": "radarr",
                    "enabled": True,
                    "host": "radarr",
                    "port": 7878,
                    "base_url": "/",
                    "use_ssl": False,
                    "http_timeout_seconds": 60,
                    "api_key": "super-secret-key",
                },
            )
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/1/edit")

    assert response.status_code == 200
    assert "super-secret-key" not in response.text  # the key is never sent to the browser
    assert "Leave blank to keep the current key" in response.text


def test_test_connection_shows_message_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/arr-services/test":
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/arr-services/test",
            data={
                "service_type": "radarr",
                "name": "radarr",
                "host": "radarr",
                "port": 7878,
                "api_key": "api-key",
            },
        )

    assert response.status_code == 200
    assert "reach the backend to run the test" in response.text


def test_toggle_enabled_reverts_switch_on_backend_error(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/arr-services/1/enabled":
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        # user tried to enable (checkbox on); backend fails → switch must revert to Disabled
        response = client.post("/settings/arr-services/1/enabled", data={"enabled": "on"})

    assert response.status_code == 200
    assert "Disabled" in response.text
    assert "checked" not in response.text


def test_edit_missing_service_redirects_to_list(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_service_handler)

    with TestClient(app) as client:
        response = client.get("/settings/arr-services/1/edit")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/arr-services/"


def test_delete_missing_service_redirects_to_list(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_missing_service_handler)

    with TestClient(app) as client:
        response = client.post("/settings/arr-services/1/delete")

    assert response.status_code == 200
    assert response.request.url.path == "/settings/arr-services/"


def test_create_shows_error_on_duplicate_name(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/arr-services/":
            return httpx.Response(
                409, json={"detail": "An arr service with this name already exists"}
            )
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.post(
            "/settings/arr-services/",
            data={
                "service_type": "radarr",
                "name": "radarr",
                "host": "radarr",
                "port": 7878,
                "api_key": "api-key",
            },
        )

    assert response.status_code == 409
    assert "already exists" in response.text
