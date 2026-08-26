import pytest
from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.authentication import api_guard
from legendarr_backend.authentication import router as authentication_router

# ROADMAP.md 0.17.0 — every router below declares its own `tags=` on its `APIRouter(...)`
# call, so Swagger UI (`/api/docs`) groups routes by domain instead of one flat list.
_TAG_BY_PREFIX = {
    "/auth": "Authentication",
    "/language-profiles": "Language Profiles",
    "/arr-services": "Arr Services",
    "/media": "Media Library",
    "/webhooks": "Webhooks",
    "/metadata-providers": "Metadata Providers",
    "/settings": "Settings",
    "/subtitle-providers": "Subtitle Providers",
    "/subtitle-proxies": "Subtitle Proxies",
    "/translation-providers": "Translation Providers",
    "/system": "System",
}


@pytest.fixture
def api_client(isolated_database, monkeypatch):
    monkeypatch.setattr(authentication_router, "get_settings", lambda: isolated_database)
    monkeypatch.setattr(api_guard, "get_settings", lambda: isolated_database)
    with TestClient(create_api_app()) as client:
        yield client


def test_every_route_is_tagged_by_its_domain(api_client):
    """A route with no matching prefix here means a new router forgot to declare
    `tags=` on its `APIRouter(...)` — that route would otherwise land in Swagger UI's
    undifferentiated "default" bucket instead of being grouped with its domain."""
    schema = api_client.get("/openapi.json").json()

    for path, operations in schema["paths"].items():
        prefix = next(p for p in _TAG_BY_PREFIX if path == p or path.startswith(p + "/"))
        expected_tag = _TAG_BY_PREFIX[prefix]
        for operation in operations.values():
            assert operation["tags"] == [expected_tag], path


def test_docs_stay_reachable_without_auth_even_when_enabled(api_client):
    """`/docs`, `/redoc`, `/openapi.json` are registered via Starlette's `add_route`
    (`fastapi.applications.FastAPI.setup`), which bypasses `create_api_app`'s app-level
    `dependencies=[Depends(require_api_access)]` — schema/documentation only, no data,
    the same posture Radarr/Sonarr/Bazarr take. This test locks that behavior in."""
    response = api_client.put(
        "/auth/settings", json={"enabled": True, "username": "admin", "password": "hunter2"}
    )
    assert response.status_code == 200

    assert api_client.get("/docs").status_code == 200
    assert api_client.get("/redoc").status_code == 200
    assert api_client.get("/openapi.json").status_code == 200
