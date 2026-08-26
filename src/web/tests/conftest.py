import os
import tempfile

import httpx
import pytest
from legendarr_web.backend_client.client import get_backend_client


@pytest.fixture(autouse=True, scope="session")
def _isolated_data_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["LEGENDARR_DATA_DIR"] = tmp_dir
        yield


def _empty_profiles_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=[])


_AUTH_DISABLED_VALIDATE_RESPONSE = {"authenticated": True, "auth_enabled": False, "session": None}


def _stub_auth_validate(handler):
    """Wrap `handler` so `POST /auth/sessions/validate` — called by the web-wide
    `require_authenticated_session` dependency on every request — always answers "auth
    is off" before reaching `handler`. Without this, every existing test's own handler
    would need to special-case that path itself just to keep working."""

    def _wrapped(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/sessions/validate":
            return httpx.Response(200, json=_AUTH_DISABLED_VALIDATE_RESPONSE)
        return handler(request)

    return _wrapped


@pytest.fixture
def stub_backend_client():
    """Override an app's `get_backend_client` dependency with a `MockTransport`.

    Defaults to a handler that returns an empty language-profiles list; pass a custom
    `handler` for tests that need different backend responses. `stub_auth_validate=False`
    opts out of the "auth is off" auto-answer on `/auth/sessions/validate` — for tests
    (`authentication/test_session_guard.py`) that want to drive that response themselves.
    """

    def _stub(app, handler=_empty_profiles_handler, stub_auth_validate=True):
        wrapped = _stub_auth_validate(handler) if stub_auth_validate else handler
        app.dependency_overrides[get_backend_client] = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(wrapped), base_url="http://backend/"
        )

    return _stub
