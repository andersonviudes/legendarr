---
name: legendarr-job-execution-budget
description: Every background job now runs under a per-queue execution budget that frees the queue slot, capped by MAX_ABANDONED_JOB_THREADS; plus register_adhoc_job, running_since, the stuck-task sweep, and the StaticPool test fixture
type: project
---

Built 2026-09-14 on branch `fix/job-execution-budget-and-cleanup`, from a user report: jobs
sometimes never finished, piled up ("encavalavam") and sat in Live Activity with a start time
days old.

**Root cause, confirmed in code:** `RunningTaskRegistry.finish()` only runs on
`EVENT_JOB_EXECUTED/ERROR/MISSED`, so a job that never returns never fires any of them and its
entry lives forever. Three consequences, all of which the user was seeing at once:
1. Its executor slot stays taken. Every `_bulk` queue is `cpu_scaled_workers()` (1–2 threads),
   so one wedged job takes out half or all of a queue's capacity.
2. A `queued` task's `started_at` is really "submitted at", so the UI shows the time it
   entered the queue — the "stale date".
3. `is_task_active(job_id)` stays `True` forever, so **that media file is never enqueued
   again by any path**. That's the real limbo, and it's per-item, not just per-queue.

**What now exists:**
- `scheduling/job_timeout.py` — `with_timeout(func, *, seconds)` runs the work on a
  `Thread(daemon=True)` and joins once; overrun raises `JobTimeoutError`, APScheduler fires
  `EVENT_JOB_ERROR`, `finish()` clears the entry and the executor slot is genuinely released.
  Module-level `configure_job_timeouts()`/`job_timeout_seconds(queue)`.
- `scheduling/scheduler.py::register_adhoc_job` — extracted from the **nine byte-identical
  `scheduler.add_job(..., "date", ...)` blocks** every slice repeated. Applies
  `with_timeout(with_retry(func))` — budget *outside* retry.
- `maintenance/reap_stuck_tasks.py` (sweep every 15 min) and `system/dismiss_running_task.py`
  + `POST /system/tasks/running/{job_id}/dismiss` (button on stalled rows only). Both evict
  and write a `JobRun` with the new `"abandoned"` status via `record_abandoned_runs`.
- `scheduled_retry` skips `JobTimeoutError`.
- Config: `<queue>_job_timeout_seconds` in `Settings` + `AppConfigFile`, `0` disables that
  queue's budget. **Changing one needs a restart** — `configure_job_timeouts` is only called
  from `bootstrap.build_scheduler()` and the budget is captured when a job is registered.

**Four things a review caught that are load-bearing — do not regress them:**
1. **`RunningTask.running_since`, not `started_at`, is the elapsed-time anchor.** A bulk
   fan-out submits thousands of jobs at once, so `started_at` can be hours old the moment a
   job actually starts. Measuring from it flagged healthy jobs as stalled, evicted them, and
   let the next fan-out enqueue a duplicate of live work. `_annotated()` stamps
   `running_since` the first time it sees a task off the queue — which is also why it writes
   back to `_tasks`: nothing else observes the queued→running transition, APScheduler emits
   events on submission and completion only.
2. **`MAX_ABANDONED_JOB_THREADS = 8`.** An abandoned thread is still in the job body holding a
   pooled DB connection (SQLAlchemy default: 5 + 10 overflow) and any
   `provider_concurrency` semaphore permit (3 per provider). Unbounded, a dead mount leaks one
   per budget period until the whole app can't reach its database — worse than the original
   wedge. At the ceiling `with_timeout` goes back to a plain `join()`, re-wedging one queue
   on purpose. `abandoned_job_threads()` prunes threads that did come back.
3. **A queue with its budget off is never evicted.** `0` is documented as removing the time
   limit; evicting on the `STALLED_TASK_THRESHOLD_SECONDS` fallback anyway would kill exactly
   the long-but-healthy runs the escape hatch exists for. Those tasks still get the badge.
4. **Queued entries are never evicted**, by the sweep or by a manual dismiss — they haven't
   started, so recording one as abandoned would be a lie.

**Defaults are per-queue, not uniform:** `ACQUIRE`/`ACQUIRE_BULK`/`UPGRADE_BULK` get 7200s
because the budget covers `with_retry`'s attempts and `speech_to_text_timeout_seconds` alone
allows 1800s per attempt with `acquisition_retry_attempts=3`. Everything else is 3600s. Size
any new queue's budget against the slowest *legitimate* run including retries — a budget that
kills healthy jobs is worse than the wedge it prevents.

**Known holes, accepted:** eviction is bookkeeping, not cancellation — a syscall-blocked
thread keeps its worker slot until restart, and on a budget-off queue APScheduler's own
`max_instances` accounting stays pinned too, so the re-enqueue a dismiss unblocks is dropped
as `EVENT_JOB_MAX_INSTANCES`. An abandoned thread may also still commit its work alongside a
second run of the same item. The real fix for both is cooperative cancellation — the
`on_progress` callbacks in `subtitle_translation/jobs.py` and `subtitle_acquisition/jobs.py`
are the natural checkpoints — deliberately not built here.

**How to apply:** every new ad-hoc per-item job goes through `register_adhoc_job`, never a
raw `add_job`. Set any attribute the sticky-cascade merge reads (`cascade`) on the *inner*
function before calling it — `with_retry` and `with_timeout` both use `functools.wraps`.

**Test-harness gotcha this forced:** job bodies now run on a spawned thread, so
`conftest.py`'s `in_memory_session` needed `StaticPool` + `check_same_thread=False`. Without
it 41 tests failed with either "SQLite objects created in a thread can only be used in that
same thread" or "no such table: movie" — the default `SingletonThreadPool` hands a new thread
a second, empty in-memory database. Production was never affected, and
`tests/scheduling/test_job_timeout.py` pins that down with a real-engine test. Tests asserting
on `stalled` must call `tasks()` once before advancing the clock, to stamp `running_since`.

See [[legendarr-hung-job-dedup-fix]] for the per-call-site fixes this generalizes, and
[[legendarr-scheduling-job-conventions]] for the registration pattern it extends.
