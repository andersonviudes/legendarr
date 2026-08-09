import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _directories_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.params.get("path", "/")
    if path == "/":
        return httpx.Response(200, json={"path": "/", "parent": None, "directories": ["media"]})
    return httpx.Response(200, json={"path": path, "parent": "/", "directories": []})


def test_browse_directories_renders_breadcrumb_and_rows(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_directories_handler)

    with TestClient(app) as client:
        response = client.get(
            "/system/directories/browse", params={"path": "/", "target": "local_path_prefix"}
        )

    assert response.status_code == 200
    assert "media" in response.text
    assert 'data-target="local_path_prefix"' in response.text


def test_browse_directories_row_links_to_subdirectory(stub_backend_client):
    app = create_app()
    stub_backend_client(app, handler=_directories_handler)

    with TestClient(app) as client:
        response = client.get(
            "/system/directories/browse", params={"path": "/", "target": "local_path_prefix"}
        )

    assert '"path": "/media"' in response.text


def test_browse_directories_renders_error_on_backend_404(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Directory not found"})

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get(
            "/system/directories/browse",
            params={"path": "/missing", "target": "local_path_prefix"},
        )

    assert response.status_code == 404
    assert "Directory not found" in response.text
