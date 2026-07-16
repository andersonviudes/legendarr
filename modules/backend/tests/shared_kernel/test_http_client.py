import httpx
import pytest
from legendarr_backend.shared_kernel.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
)


def _client_with_transport(handler) -> ProviderHttpClient:
    client = ProviderHttpClient("TestProvider", "http://provider.local")
    client._client = httpx.Client(
        base_url="http://provider.local", transport=httpx.MockTransport(handler)
    )
    return client


def test_get_json_returns_parsed_body_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1}])

    client = _client_with_transport(handler)

    assert client.get_json("/items") == [{"id": 1}]


def test_get_json_wraps_http_status_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider.*500"):
        client.get_json("/items")


def test_get_json_wraps_request_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider"):
        client.get_json("/items")
