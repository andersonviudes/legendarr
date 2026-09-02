from datetime import UTC, datetime, timedelta

from legendarr_backend.scheduling.circuit_breaker import (
    FAILURE_THRESHOLD,
    BreakerCategory,
    BreakerSnapshot,
    CircuitBreakerRegistry,
    is_open,
    record_failure,
    reset_circuit_breakers,
)


def test_a_provider_starts_closed():
    registry = CircuitBreakerRegistry()

    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is False


def test_opens_after_reaching_the_failure_threshold():
    registry = CircuitBreakerRegistry()
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")

    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is True


def test_stays_closed_below_the_failure_threshold():
    registry = CircuitBreakerRegistry()
    for _ in range(FAILURE_THRESHOLD - 1):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")

    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is False


def test_a_success_before_the_threshold_resets_the_streak():
    registry = CircuitBreakerRegistry()
    for _ in range(FAILURE_THRESHOLD - 1):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")
    registry.record_success(BreakerCategory.TRANSLATION, "deepl")
    for _ in range(FAILURE_THRESHOLD - 1):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")

    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is False


def test_stays_open_before_the_cooldown_elapses():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)

    still_within_cooldown = opened_at + timedelta(minutes=1)
    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl", now=still_within_cooldown) is True


def test_allows_a_half_open_trial_once_the_cooldown_elapses():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)

    past_cooldown = opened_at + timedelta(minutes=10)
    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl", now=past_cooldown) is False


def test_a_successful_half_open_trial_closes_the_circuit():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)
    registry.record_success(BreakerCategory.TRANSLATION, "deepl")

    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is False
    for _ in range(FAILURE_THRESHOLD - 1):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")
    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl") is False


def test_a_failed_half_open_trial_reopens_for_another_full_cooldown():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)
    trial_time = opened_at + timedelta(minutes=10)
    registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=trial_time)

    just_after_trial = trial_time + timedelta(minutes=1)
    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl", now=just_after_trial) is True
    past_new_cooldown = trial_time + timedelta(minutes=10)
    assert registry.is_open(BreakerCategory.TRANSLATION, "deepl", now=past_new_cooldown) is False


def test_categories_never_share_state_even_with_the_same_provider_name():
    registry = CircuitBreakerRegistry()
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "shared-name")

    assert registry.is_open(BreakerCategory.TRANSLATION, "shared-name") is True
    assert registry.is_open(BreakerCategory.ACQUISITION, "shared-name") is False


def test_module_level_functions_share_one_registry():
    reset_circuit_breakers()
    try:
        for _ in range(FAILURE_THRESHOLD):
            record_failure(BreakerCategory.TRANSLATION, "deepl")

        assert is_open(BreakerCategory.TRANSLATION, "deepl") is True
    finally:
        reset_circuit_breakers()


def test_get_state_for_a_provider_that_never_failed():
    registry = CircuitBreakerRegistry()

    snapshot = registry.get_state(BreakerCategory.TRANSLATION, "deepl")

    assert snapshot == BreakerSnapshot(is_open=False, consecutive_failures=0, opened_at=None)


def test_get_state_reflects_failures_below_the_threshold():
    registry = CircuitBreakerRegistry()
    for _ in range(FAILURE_THRESHOLD - 1):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl")

    snapshot = registry.get_state(BreakerCategory.TRANSLATION, "deepl")

    assert snapshot.is_open is False
    assert snapshot.consecutive_failures == FAILURE_THRESHOLD - 1
    assert snapshot.opened_at is None


def test_get_state_reflects_an_open_circuit():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)

    snapshot = registry.get_state(BreakerCategory.TRANSLATION, "deepl", now=opened_at)

    assert snapshot.is_open is True
    assert snapshot.consecutive_failures == FAILURE_THRESHOLD
    assert snapshot.opened_at == opened_at


def test_get_state_reports_closed_but_keeps_the_failure_count_past_cooldown():
    registry = CircuitBreakerRegistry()
    opened_at = datetime.now(UTC)
    for _ in range(FAILURE_THRESHOLD):
        registry.record_failure(BreakerCategory.TRANSLATION, "deepl", now=opened_at)

    past_cooldown = opened_at + timedelta(minutes=10)
    snapshot = registry.get_state(BreakerCategory.TRANSLATION, "deepl", now=past_cooldown)

    assert snapshot.is_open is False
    assert snapshot.consecutive_failures == FAILURE_THRESHOLD
    assert snapshot.opened_at == opened_at
