import pytest
from legendarr_backend.scheduling.retry import with_retry


def test_with_retry_succeeds_after_transient_failures():
    calls = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("boom")
        return "ok"

    result = with_retry(flaky, max_attempts=3, delay_seconds=0)()

    assert result == "ok"
    assert len(calls) == 3


def test_with_retry_raises_after_exhausting_attempts():
    calls = []

    def always_fails() -> None:
        calls.append(1)
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        with_retry(always_fails, max_attempts=3, delay_seconds=0)()

    assert len(calls) == 3
