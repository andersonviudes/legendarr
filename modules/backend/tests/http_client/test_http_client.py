import httpx
import pytest
from legendarr_backend.http_client.client import (
    ProviderClientError,
    ProviderHttpClient,
    describe_error,
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


def test_init_honors_custom_timeout():
    client = ProviderHttpClient("TestProvider", "http://provider.local", timeout=5.0)

    assert client._client.timeout.connect == 5.0


def test_post_json_returns_parsed_body_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"token": "abc"})

    client = _client_with_transport(handler)

    assert client.post_json("/login", {"username": "a"}) == {"token": "abc"}


def test_post_json_wraps_http_status_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad credentials"})

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider.*401"):
        client.post_json("/login", {"username": "a"})


def test_post_json_wraps_request_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider"):
        client.post_json("/login", {"username": "a"})


def test_ping_succeeds_without_a_json_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ok</html>")

    client = _client_with_transport(handler)

    client.ping("/")


def test_ping_wraps_http_status_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider.*500"):
        client.ping("/")


def test_ping_follows_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "http://provider.local/canonical"})
        return httpx.Response(200, text="<html>ok</html>")

    client = _client_with_transport(handler)

    client.ping("/")


def test_request_does_not_raise_on_a_non_2xx_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, text="redirecting")

    client = _client_with_transport(handler)

    response = client.request("POST", "/login", data={"username": "a"}, follow_redirects=False)

    assert response.status_code == 302


def test_request_wraps_connection_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(handler)

    with pytest.raises(ProviderClientError, match="TestProvider"):
        client.request("GET", "/")


def test_describe_error_flags_rejected_credentials():
    request = httpx.Request("GET", "http://provider.local/items")
    response = httpx.Response(401, request=request)
    cause = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
    try:
        raise ProviderClientError("boom") from cause
    except ProviderClientError as exc:
        assert "API Key" in describe_error(exc)


def test_describe_error_falls_back_to_str_for_other_errors():
    exc = ProviderClientError("unreachable")

    assert describe_error(exc) == "unreachable"
