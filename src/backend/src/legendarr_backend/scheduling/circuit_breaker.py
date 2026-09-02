import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

# A provider opens after this many consecutive failures — one blip shouldn't trip it,
# but a real streak should stop hammering it on every remaining media file's job.
FAILURE_THRESHOLD = 3
# How long an open circuit stays open before a half-open trial call is let through.
COOLDOWN_SECONDS = 300.0


class BreakerCategory(StrEnum):
    """Which provider chain a breaker key belongs to — kept distinct so a translation
    provider and an acquisition provider can never share breaker state even if they
    happened to have the same `name`.
    """

    TRANSLATION = "translation"
    ACQUISITION = "acquisition"


@dataclass
class _BreakerState:
    consecutive_failures: int = 0
    opened_at: datetime | None = None


@dataclass(frozen=True)
class BreakerSnapshot:
    """Point-in-time read of one provider's breaker state, for the System > Providers
    status page (`system/provider_status.py`) — unlike `is_open`, exposes the failure
    count and open timestamp behind that bool instead of collapsing them away.
    """

    is_open: bool
    consecutive_failures: int
    opened_at: datetime | None


def _state_is_open(state: _BreakerState | None, now: datetime) -> bool:
    if state is None or state.opened_at is None:
        return False
    return now - state.opened_at < timedelta(seconds=COOLDOWN_SECONDS)


class CircuitBreakerRegistry:
    """Tracks per-provider failure streaks for the translation/acquisition provider
    chains, so a provider that's already failing gets skipped instead of hit again on
    every media file's job.

    Keyed by `(category, provider_name)`. After `FAILURE_THRESHOLD` consecutive
    failures the circuit opens: `is_open` returns `True` until `COOLDOWN_SECONDS` have
    passed since it opened, then returns `False` once — a half-open trial — leaving it
    to the caller's own `record_success`/`record_failure` to decide whether it closes
    or reopens for another full cooldown. State resets on restart — same posture as
    `RunningTaskRegistry` (`scheduling/running_tasks.py`): this is live backoff state,
    not a persisted history. Submission and completion can arrive from different
    executor worker threads, so access is locked.
    """

    def __init__(self) -> None:
        self._breakers: dict[tuple[BreakerCategory, str], _BreakerState] = {}
        self._lock = threading.Lock()

    def is_open(
        self, category: BreakerCategory, provider: str, *, now: datetime | None = None
    ) -> bool:
        now = now if now is not None else datetime.now(UTC)
        with self._lock:
            state = self._breakers.get((category, provider))
            return _state_is_open(state, now)

    def get_state(
        self, category: BreakerCategory, provider: str, *, now: datetime | None = None
    ) -> BreakerSnapshot:
        now = now if now is not None else datetime.now(UTC)
        with self._lock:
            state = self._breakers.get((category, provider))
            return BreakerSnapshot(
                is_open=_state_is_open(state, now),
                consecutive_failures=state.consecutive_failures if state is not None else 0,
                opened_at=state.opened_at if state is not None else None,
            )

    def record_success(self, category: BreakerCategory, provider: str) -> None:
        with self._lock:
            self._breakers.pop((category, provider), None)

    def record_failure(
        self, category: BreakerCategory, provider: str, *, now: datetime | None = None
    ) -> None:
        now = now if now is not None else datetime.now(UTC)
        with self._lock:
            key = (category, provider)
            state = self._breakers.setdefault(key, _BreakerState())
            state.consecutive_failures += 1
            if state.consecutive_failures >= FAILURE_THRESHOLD:
                state.opened_at = now

    def clear(self) -> None:
        with self._lock:
            self._breakers.clear()


_registry = CircuitBreakerRegistry()


def is_open(category: BreakerCategory, provider: str, *, now: datetime | None = None) -> bool:
    """Whether `provider` (within `category`) is currently backing off and should be
    skipped rather than called.
    """
    return _registry.is_open(category, provider, now=now)


def get_state(
    category: BreakerCategory, provider: str, *, now: datetime | None = None
) -> BreakerSnapshot:
    """Current failure-streak/circuit state for `provider` (within `category`) — for the
    System > Providers status page. Read-only: unlike `is_open`, callers don't use this
    to decide whether to skip a call.
    """
    return _registry.get_state(category, provider, now=now)


def record_success(category: BreakerCategory, provider: str) -> None:
    """Report that a call to `provider` succeeded, closing its circuit if it was open."""
    _registry.record_success(category, provider)


def record_failure(
    category: BreakerCategory, provider: str, *, now: datetime | None = None
) -> None:
    """Report that a call to `provider` failed, opening its circuit once
    `FAILURE_THRESHOLD` consecutive failures are reached."""
    _registry.record_failure(category, provider, now=now)


def reset_circuit_breakers() -> None:
    """Clear all in-memory circuit-breaker state. For test isolation only."""
    _registry.clear()
