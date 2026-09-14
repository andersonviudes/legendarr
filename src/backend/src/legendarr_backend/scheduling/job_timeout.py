import functools
import logging
import threading
from collections.abc import Callable

from legendarr_backend.scheduling.queues import JOB_TIMEOUT_SECONDS, JobQueue

logger = logging.getLogger(__name__)


class JobTimeoutError(TimeoutError):
    """Raised when a job outlives its queue's execution budget.

    Its own type rather than a bare `TimeoutError` so callers can tell "this run was cut
    off for taking too long" apart from a timeout raised by the work itself (an HTTP
    read timeout, `ffsubsync` giving up) — `scheduling/scheduled_retry.py` uses exactly
    that distinction to decide not to re-enqueue the run.
    """


_timeouts: dict[JobQueue, float] = dict(JOB_TIMEOUT_SECONDS)
_timeouts_lock = threading.Lock()

# Ceiling on how many abandoned job threads may be alive at once, process-wide.
#
# Abandoning a thread doesn't only leak memory: the thread is still inside the job body,
# so it keeps whatever that body holds — a `database/engine.py` pooled connection with an
# open transaction (SQLAlchemy's default QueuePool is 5 + 10 overflow), and any
# `scheduling/provider_concurrency.py` semaphore permit (3 per provider). Left unbounded
# that turns a wedged mount into a whole-process outage: every queue keeps dispatching
# into the same dead path, leaks another connection each budget period, and eventually
# every request in the app blocks on pool checkout.
#
# So the budget stops being unconditional past this point. At the ceiling a timed-out run
# goes back to waiting on its thread, which re-wedges that one worker slot — the original
# bug, deliberately, because one stuck queue is a much smaller failure than a process that
# can't reach its database. Set below the pool's 15 so the app stays usable either way.
MAX_ABANDONED_JOB_THREADS = 8

_abandoned_threads: list[threading.Thread] = []
_abandoned_lock = threading.Lock()


def abandoned_job_threads() -> int:
    """How many abandoned job threads are still alive, pruning the ones that eventually
    finished on their own. A slow job that outran its budget but did come back releases
    its place here, so only genuinely-wedged threads count against the ceiling."""
    with _abandoned_lock:
        _abandoned_threads[:] = [thread for thread in _abandoned_threads if thread.is_alive()]
        return len(_abandoned_threads)


def _try_abandon(thread: threading.Thread) -> bool:
    """Claim one of the `MAX_ABANDONED_JOB_THREADS` slots for `thread`, or report that
    none is left."""
    with _abandoned_lock:
        _abandoned_threads[:] = [alive for alive in _abandoned_threads if alive.is_alive()]
        if len(_abandoned_threads) >= MAX_ABANDONED_JOB_THREADS:
            return False
        _abandoned_threads.append(thread)
        return True


def configure_job_timeouts(timeouts: dict[JobQueue, float]) -> None:
    """Override the per-queue execution budgets `job_timeout_seconds` reports.

    Called once at startup from `legendarr_backend.bootstrap.build_scheduler()` with the
    map built from `AppConfigFile`'s `<queue>_job_timeout_seconds` fields — once, which is
    why editing those values needs a restart to take effect. Module-level
    state rather than a parameter threaded through every job registration, for the same
    reason `scheduling/running_tasks.py` keeps a module-level registry: the budget is
    needed at ~20 call sites across 8 slices (10 `register_*_job`s and 9 ad-hoc
    `enqueue_*`s, several of which are called from routers, webhooks and cross-slice
    cascades), and none of them has any other reason to know about config.
    """
    with _timeouts_lock:
        _timeouts.update(timeouts)


def job_timeout_seconds(queue: JobQueue) -> float:
    """This queue's per-execution budget in seconds; `<= 0` means no budget at all.

    Falls back to `JOB_TIMEOUT_SECONDS`'s default for a queue nobody configured, so a
    partial override (a test, a `config.yaml` written before a queue existed) is safe.
    """
    with _timeouts_lock:
        return _timeouts.get(queue, JOB_TIMEOUT_SECONDS[queue])


def reset_job_timeouts() -> None:
    """Restore the built-in per-queue budgets. For test isolation only."""
    with _timeouts_lock:
        _timeouts.clear()
        _timeouts.update(JOB_TIMEOUT_SECONDS)
    with _abandoned_lock:
        _abandoned_threads.clear()


def with_timeout[T](func: Callable[[], T], *, seconds: float) -> Callable[[], T]:
    """Wrap `func` so a run that outlives `seconds` is abandoned and raises.

    The work runs on a `Thread(daemon=True)` that is joined exactly once, never waited on
    again — the same shape `subtitle_acquisition/provider_search.py::_search_all`,
    `opensubtitles_hash` and `audio_transcription/transcribe_audio.py` already use, and
    for the same reason: a thread blocked in a syscall (a read off a network mount that
    stopped answering) can't be interrupted from Python, so the only way to get the
    caller's thread back is to stop waiting for it. What's new here is that the caller's
    thread is an APScheduler executor worker, so letting go of it is what frees the
    queue's slot instead of wedging it until the process restarts.

    Raising (rather than returning quietly) is deliberate: APScheduler turns it into
    `EVENT_JOB_ERROR`, which is what makes `RunningTaskRegistry.finish()` drop the
    registry entry — and dropping that entry is what lets `is_task_active()` stop
    reporting the job as in flight forever, so the item can be enqueued again.

    The abandoned thread keeps running and may still commit its work minutes later, after
    the run has already been recorded as failed — and, because the registry entry is gone,
    possibly alongside a second run of the same item that the next fan-out enqueued. That's
    accepted, same as `_transcribe_with_timeout`: the alternative is a cancellation token
    every long loop would have to check. What is *not* accepted is an unbounded number of
    them, which is what `MAX_ABANDONED_JOB_THREADS` caps — see its comment.

    `seconds <= 0` disables the budget and returns `func` untouched.
    """
    if seconds <= 0:
        return func

    @functools.wraps(func)
    def wrapped() -> T:
        result: list[T] = []
        error: list[Exception] = []

        def target() -> None:
            try:
                result.append(func())
            except Exception as exc:
                error.append(exc)

        thread = threading.Thread(target=target, daemon=True, name=f"job:{func.__name__}")
        thread.start()
        thread.join(timeout=seconds)
        if thread.is_alive() and not _try_abandon(thread):
            logger.error(
                "%s exceeded its %.0fs execution budget, but %d job threads are already "
                "abandoned — waiting on this one instead of leaking another. Its queue is "
                "blocked until it returns or legendarr restarts",
                func.__name__,
                seconds,
                MAX_ABANDONED_JOB_THREADS,
            )
            thread.join()
        elif thread.is_alive():
            logger.warning(
                "%s exceeded its %.0fs execution budget — abandoning its thread and "
                "releasing the queue slot; the run is recorded as failed",
                func.__name__,
                seconds,
            )
            raise JobTimeoutError(f"{func.__name__} exceeded its {seconds:.0f}s execution budget")
        if error:
            raise error[0]
        if not result:
            # `except Exception` above doesn't cover a `BaseException` (a `SystemExit`
            # raised inside the job, say), which kills the thread with neither list
            # filled. Say so rather than failing on an IndexError.
            raise RuntimeError(f"{func.__name__} ended without producing a result")
        return result[0]

    return wrapped
