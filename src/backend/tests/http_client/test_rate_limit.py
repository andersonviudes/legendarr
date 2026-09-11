import httpx
import pytest
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.http_client.rate_limit import (
    RATE_LIMIT_MAX_DELAY_SECONDS,
    retry_on_rate_limit,
)


def _client_with_transport(handler) -> ProviderHttpClient:
    client = ProviderHttpClient("TestProvider", "http://provider.local")
    client._client = httpx.Client(
        base_url="http://provider.local", transport=httpx.MockTransport(handler)
    )
    return client


@pytest.fixture
def slept(monkeypatch) -> list[float]:
    """Record every backoff wait instead of actually sleeping, so the retry timing is
    assertable and the suite stays fast."""
    recorded: list[float] = []
    monkeypatch.setattr("legendarr_backend.http_client.rate_limit.time.sleep", recorded.append)
    return recorded


def _responder(statuses: list[int], headers: dict[str, str] | None = None):
    """A handler returning `statuses` in order, then 200 forever after."""
    remaining = list(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        if remaining:
            return httpx.Response(remaining.pop(0), json={"error": "slow down"}, headers=headers)
        return httpx.Response(200, json={"ok": True})

    return handler


def test_returns_the_result_without_sleeping_when_the_call_succeeds(slept):
    client = _client_with_transport(_responder([]))

    result = retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert result == {"ok": True}
    assert slept == []


def test_retries_a_429_and_returns_the_eventual_success(slept):
    client = _client_with_transport(_responder([429, 429]))

    result = retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert result == {"ok": True}
    assert len(slept) == 2


def test_backoff_grows_between_attempts(slept):
    client = _client_with_transport(_responder([429, 429]))

    retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert slept[1] > slept[0]


def test_reraises_the_429_once_attempts_are_exhausted(slept):
    client = _client_with_transport(_responder([429, 429, 429, 429]))

    with pytest.raises(ProviderClientError, match="429"):
        retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    # Three waits for four attempts — the last failure is raised, not slept on.
    assert len(slept) == 3


def test_honors_max_attempts_override(slept):
    client = _client_with_transport(_responder([429, 429, 429, 429]))

    with pytest.raises(ProviderClientError):
        retry_on_rate_limit(
            lambda: client.get_json("/items"), description="TestProvider", max_attempts=2
        )

    assert len(slept) == 1


def test_does_not_retry_a_non_rate_limit_status(slept):
    client = _client_with_transport(_responder([401]))

    with pytest.raises(ProviderClientError, match="401"):
        retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert slept == []


def test_does_not_retry_an_unrelated_exception(slept):
    def call() -> None:
        raise ValueError("not an HTTP failure")

    with pytest.raises(ValueError):
        retry_on_rate_limit(call, description="TestProvider")

    assert slept == []


def test_honors_a_retry_after_header(slept):
    client = _client_with_transport(_responder([429], headers={"Retry-After": "7"}))

    retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert slept == [7.0]


def test_falls_back_to_backoff_for_an_unparseable_retry_after(slept):
    client = _client_with_transport(
        _responder([429], headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    )

    retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert slept and slept[0] > 0


def test_gives_up_when_retry_after_exceeds_the_cap(slept):
    retry_after = str(int(RATE_LIMIT_MAX_DELAY_SECONDS) + 1)
    client = _client_with_transport(_responder([429], headers={"Retry-After": retry_after}))

    with pytest.raises(ProviderClientError, match="429"):
        retry_on_rate_limit(lambda: client.get_json("/items"), description="TestProvider")

    assert slept == []
