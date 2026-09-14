import functools
import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


def with_retry[T](
    func: Callable[[], T], *, max_attempts: int, delay_seconds: float
) -> Callable[[], T]:
    """Wrap `func` so it retries on exception, with a fixed delay between attempts.

    Re-raises the last exception once `max_attempts` is exhausted, so the caller (e.g.
    APScheduler) still observes the run as failed.

    `functools.wraps` also copies `func.__dict__` onto the wrapper, which is what keeps
    the `cascade` flag `enqueue_*` sets on the job function visible as
    `scheduler.get_job(job_id).func.cascade` — the sticky-cascade merge in
    `media_library/jobs.py`, `subtitle_acquisition/jobs.py` and
    `subtitle_discovery/jobs.py` reads it off whatever callable actually reached the
    jobstore, which is this wrapper (and then `with_timeout`'s on top of it).
    """

    @functools.wraps(func)
    def wrapped() -> T:
        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except Exception:
                if attempt == max_attempts:
                    logger.exception("%s failed after %d attempts", func.__name__, max_attempts)
                    raise
                logger.warning(
                    "%s failed on attempt %d/%d, retrying in %.1fs",
                    func.__name__,
                    attempt,
                    max_attempts,
                    delay_seconds,
                )
                time.sleep(delay_seconds)
        raise AssertionError("unreachable")  # max_attempts is always >= 1

    return wrapped
