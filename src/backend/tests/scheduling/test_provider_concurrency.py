import threading
import time

from legendarr_backend.scheduling.provider_concurrency import (
    PROVIDER_MAX_CONCURRENCY,
    ConcurrencyCategory,
    ProviderConcurrencyRegistry,
    limit_concurrency,
    reset_provider_concurrency,
)


def test_allows_up_to_the_concurrency_limit_at_once():
    registry = ProviderConcurrencyRegistry()
    semaphore = registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles")

    for _ in range(PROVIDER_MAX_CONCURRENCY):
        assert semaphore.acquire(blocking=False) is True


def test_blocks_beyond_the_concurrency_limit():
    registry = ProviderConcurrencyRegistry()
    semaphore = registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles")
    for _ in range(PROVIDER_MAX_CONCURRENCY):
        semaphore.acquire()

    assert semaphore.acquire(blocking=False) is False


def test_categories_never_share_a_semaphore_even_with_the_same_provider_name():
    registry = ProviderConcurrencyRegistry()
    semaphore = registry.limit(ConcurrencyCategory.ACQUISITION, "shared-name")
    for _ in range(PROVIDER_MAX_CONCURRENCY):
        semaphore.acquire()

    other = registry.limit(ConcurrencyCategory.TRANSLATION, "shared-name")
    assert other.acquire(blocking=False) is True


def test_providers_never_share_a_semaphore_even_within_the_same_category():
    registry = ProviderConcurrencyRegistry()
    semaphore = registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles")
    for _ in range(PROVIDER_MAX_CONCURRENCY):
        semaphore.acquire()

    other = registry.limit(ConcurrencyCategory.ACQUISITION, "subdl")
    assert other.acquire(blocking=False) is True


def test_the_same_key_always_returns_the_same_semaphore_instance():
    registry = ProviderConcurrencyRegistry()

    first = registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles")
    second = registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles")

    assert first is second


def test_limit_concurrency_caps_actual_concurrent_execution():
    registry = ProviderConcurrencyRegistry()
    concurrent_now = 0
    peak = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal concurrent_now, peak
        with registry.limit(ConcurrencyCategory.ACQUISITION, "opensubtitles"):
            with lock:
                concurrent_now += 1
                peak = max(peak, concurrent_now)
            time.sleep(0.05)
            with lock:
                concurrent_now -= 1

    threads = [threading.Thread(target=worker) for _ in range(PROVIDER_MAX_CONCURRENCY + 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == PROVIDER_MAX_CONCURRENCY


def test_module_level_function_shares_one_registry():
    reset_provider_concurrency()
    try:
        semaphore = limit_concurrency(ConcurrencyCategory.ACQUISITION, "opensubtitles")
        for _ in range(PROVIDER_MAX_CONCURRENCY):
            semaphore.acquire()

        assert (
            limit_concurrency(ConcurrencyCategory.ACQUISITION, "opensubtitles").acquire(
                blocking=False
            )
            is False
        )
    finally:
        reset_provider_concurrency()
