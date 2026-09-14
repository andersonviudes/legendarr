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


def test_with_retry_preserves_attributes_set_on_the_wrapped_function():
    """`enqueue_*`'s sticky-cascade merge reads `scheduler.get_job(job_id).func.cascade`
    off whatever callable reached the jobstore — the wrapper must not hide it."""

    def work() -> None:
        pass

    work.cascade = True  # type: ignore[attr-defined]

    wrapped = with_retry(work, max_attempts=1, delay_seconds=0)

    assert getattr(wrapped, "cascade", False) is True
    assert wrapped.__name__ == "work"
