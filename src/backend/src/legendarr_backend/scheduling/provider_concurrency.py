import threading
from enum import StrEnum

# How many concurrent calls to the same provider are allowed at once, regardless of how
# many bulk-queue workers happen to be processing different media files/items in
# parallel — the safety net that makes `queues.cpu_scaled_workers()` safe to use for a
# provider-facing queue: raising the worker count only raises how many items are in
# flight, never how hard a single provider gets hit.
PROVIDER_MAX_CONCURRENCY = 3


class ConcurrencyCategory(StrEnum):
    """Which provider chain a concurrency key belongs to — kept distinct so a
    translation provider and an acquisition provider can never share a semaphore even if
    they happened to have the same `name`. Deliberately not
    `circuit_breaker.BreakerCategory`: this registry also covers `media_metadata`, which
    has no circuit breaker of its own.
    """

    TRANSLATION = "translation"
    ACQUISITION = "acquisition"
    METADATA = "metadata"


class ProviderConcurrencyRegistry:
    """Caps how many calls to the same provider can run at once, across every bulk-queue
    worker thread that might be calling it concurrently.

    Keyed by `(category, provider_name)`, same shape as
    `circuit_breaker.CircuitBreakerRegistry`. A semaphore is created lazily on first use
    and reused for the life of the process — state resets on restart, same posture as
    the circuit breaker. Submission and completion can arrive from different executor
    worker threads, so access is locked.
    """

    def __init__(self) -> None:
        self._semaphores: dict[tuple[ConcurrencyCategory, str], threading.BoundedSemaphore] = {}
        self._lock = threading.Lock()

    def limit(self, category: ConcurrencyCategory, provider: str) -> threading.BoundedSemaphore:
        key = (category, provider)
        with self._lock:
            semaphore = self._semaphores.get(key)
            if semaphore is None:
                semaphore = threading.BoundedSemaphore(PROVIDER_MAX_CONCURRENCY)
                self._semaphores[key] = semaphore
            return semaphore

    def clear(self) -> None:
        with self._lock:
            self._semaphores.clear()


_registry = ProviderConcurrencyRegistry()


def limit_concurrency(category: ConcurrencyCategory, provider: str) -> threading.BoundedSemaphore:
    """A context manager capping concurrent calls to `provider` (within `category`) at
    `PROVIDER_MAX_CONCURRENCY`: wrap a search/download/fetch call with
    `with limit_concurrency(...):` so raising a bulk queue's worker count never lets a
    beefier host hit the same rate-limited provider harder than a smaller one would.
    """
    return _registry.limit(category, provider)


def reset_provider_concurrency() -> None:
    """Clear all in-memory concurrency state. For test isolation only."""
    _registry.clear()
