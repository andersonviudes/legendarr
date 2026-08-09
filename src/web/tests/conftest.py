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


@pytest.fixture
def stub_backend_client():
    """Override an app's `get_backend_client` dependency with a `MockTransport`.

    Defaults to a handler that returns an empty language-profiles list; pass a custom
    `handler` for tests that need different backend responses.
    """

    def _stub(app, handler=_empty_profiles_handler):
        app.dependency_overrides[get_backend_client] = lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://backend/"
        )

    return _stub
