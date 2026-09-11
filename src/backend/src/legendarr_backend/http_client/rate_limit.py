"""Retry-with-backoff for provider calls a rate limiter rejected.

`ProviderHttpClient`'s transport-level retries (`httpx.HTTPTransport(retries=...)`) only
cover connection failures — an HTTP 429 comes back as a `ProviderClientError` on the very
first try, with no wait. That's the right default for the providers we call once per
subtitle, but not for the ones where being rate-limited is the expected steady state:
Google's keyless endpoint (one request per subtitle line) and free-tier LLM APIs.
"""

import logging
import random
import time
from collections.abc import Callable

import httpx

from legendarr_backend.http_client.client import ProviderClientError

logger = logging.getLogger(__name__)

# How many attempts a rate-limited call gets before its 429 is re-raised, and the wait
# between them: `BASE * 2 ** (attempt - 1)` plus up to a second of jitter, capped at MAX so
# one unlucky call can't hold a bulk-queue worker indefinitely. Hardcoded module constants
# rather than `Settings` fields, same posture as `scheduling/circuit_breaker.py`'s
# thresholds — internal resilience policy, not user-facing tuning.
RATE_LIMIT_MAX_ATTEMPTS = 4
RATE_LIMIT_BASE_DELAY_SECONDS = 1.0
RATE_LIMIT_MAX_DELAY_SECONDS = 30.0

_TOO_MANY_REQUESTS = 429


def _rate_limit_response(exc: ProviderClientError) -> httpx.Response | None:
    """The 429 response behind `exc`, or `None` if it wasn't a rate-limit rejection.
    Reads `__cause__` the same way `client.describe_error` does — `ProviderHttpClient`
    always chains the original `httpx` error there."""
    cause = exc.__cause__
    if isinstance(cause, httpx.HTTPStatusError):
        if cause.response.status_code == _TOO_MANY_REQUESTS:
            return cause.response
    return None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """`Retry-After` as seconds, when the server sent a usable one. Only the
    delta-seconds form is honored — the HTTP-date form is legal but none of the providers
    we call uses it, and guessing at clock skew is worse than our own backoff.
    """
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        return max(0.0, float(header.strip()))
    except ValueError:
        return None


def _backoff_seconds(attempt: int) -> float:
    exponential = RATE_LIMIT_BASE_DELAY_SECONDS * 2 ** (attempt - 1)
    return min(exponential, RATE_LIMIT_MAX_DELAY_SECONDS) + random.uniform(0, 1)


def _delay_before_retry(response: httpx.Response, attempt: int) -> float | None:
    """How long to wait before the next attempt, or `None` to give up now. A server that
    asks for longer than `RATE_LIMIT_MAX_DELAY_SECONDS` is taken at its word and the call
    is abandoned rather than parked — the circuit breaker is the right place to absorb a
    provider that's out of quota for the next hour, not a sleeping worker thread.
    """
    retry_after = _retry_after_seconds(response)
    if retry_after is None:
        return _backoff_seconds(attempt)
    if retry_after > RATE_LIMIT_MAX_DELAY_SECONDS:
        return None
    return retry_after


def retry_on_rate_limit[T](
    call: Callable[[], T],
    *,
    description: str,
    max_attempts: int = RATE_LIMIT_MAX_ATTEMPTS,
) -> T:
    """Run `call`, retrying only while it fails with an HTTP 429.

    Every other failure propagates on the first attempt — a 401 or a malformed request
    never gets better by waiting. The final 429 is re-raised once `max_attempts` is
    exhausted, so the caller still observes a failure and the circuit breaker still counts
    it. `description` names the call in the retry log line (e.g. "Google Translate").
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return call()
        except ProviderClientError as exc:
            response = _rate_limit_response(exc)
            if response is None or attempt == max_attempts:
                raise
            delay = _delay_before_retry(response, attempt)
            if delay is None:
                raise
            logger.warning(
                "%s was rate-limited on attempt %d/%d, retrying in %.1fs",
                description,
                attempt,
                max_attempts,
                delay,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # max_attempts is always >= 1
