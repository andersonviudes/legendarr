---
name: legendarr scheduling/job conventions
description: How background jobs are registered in legendarr backend — shared scheduling/ module + per-slice jobs.py, required pattern for any new APScheduler job
type: project
---

Built 2026-07-16 on branch `feat/scheduling-job-conventions`, completing the "Automation &
scheduling" bullet of `ROADMAP.md` 0.1.0. Before this, `bootstrap.py` built a bare
`BackgroundScheduler()` and called `add_job(run_sync, "interval", minutes=...)` directly, with
no job id, no executor/queue, no `max_instances`/`coalesce`, and no retry-on-failure — it was
the only job that existed.

**What exists:** a shared top-level `legendarr_backend/scheduling/` module (same tier as
`http_client/`) — `queues.py` (`JobQueue` `StrEnum`, currently only `SYNC`; `QUEUE_WORKERS`
maps each queue to its executor's thread count), `retry.py` (`with_retry(func, *,
max_attempts, delay_seconds)` — synchronous retry wrapper, mirrors how `ProviderHttpClient`
wraps `httpx.HTTPTransport(retries=...)`), `scheduler.py` (`build_scheduler()` builds a
`BackgroundScheduler` with one `apscheduler.executors.pool.ThreadPoolExecutor` per queue —
note: must import APScheduler's own `ThreadPoolExecutor`, not `concurrent.futures`'s, or
`add_job` raises `TypeError`; `register_job(scheduler, func, *, queue, job_id, trigger,
retry_attempts, retry_delay_seconds, max_instances, coalesce, **trigger_args)` wraps `func`
with `with_retry` and calls `scheduler.add_job(..., executor=queue.value,
replace_existing=True, ...)`). `scheduling/` itself never references a concrete job.

Each slice that needs a background job owns its own `<slice>/jobs.py` exposing
`register_<name>_job(scheduler, ...)`, which owns that job's concrete wiring (queue, trigger,
retry/concurrency policy) and calls `scheduling.scheduler.register_job(...)`. Today that's
`media_library/jobs.py::register_sync_job`. `bootstrap.py` stays a thin composition root: it
builds shared dependencies (scheduler, config, media clients) and calls each slice's
`register_*_job` explicitly — one import + one call per job — the exact same shape `api.py`
already uses for routers (`from legendarr_backend.language_profiles.router import router as
language_profiles_router` + `app.include_router(language_profiles_router)` in
`create_api_app()`).

Per-job retry/concurrency policy is config-driven, following the existing
`sync_interval_minutes` pattern: `sync_retry_attempts` (default 3), `sync_retry_delay_seconds`
(default 5.0), `sync_max_instances` (default 1), `sync_coalesce` (default `True`) were added to
both `Settings` (env-derived bootstrap default) and `AppConfigFile` (runtime-persisted,
backfilled from `Settings`).

**Why split this way:** confirmed by the user explicitly — "cada pasta de negocio pode ter seu
job, igual a api, e bootstrap registra esses jobs" (each business slice can have its own job,
like the API routers, and bootstrap registers them). Keeps `scheduling/` job-agnostic (no
media_library-specific knowledge leaks into shared infra) and keeps `bootstrap.py` from
growing one hardcoded queue/trigger/retry block per job type as the 0.9.0 "Unattended
scheduling" roadmap item adds more jobs — avoids the god-function/SRP issue flagged in
`.claudin/rules/clean-code-solid.md`.

**How to apply:** when adding a new background job in any slice, (1) add a new `JobQueue`
member only if the job genuinely needs its own concurrency pool — don't pre-create queues
speculatively (YAGNI); (2) add a `<slice>/jobs.py` with `register_<name>_job(scheduler, ...)`
that calls `scheduling.scheduler.register_job(...)`; (3) wire it into `bootstrap.py` with one
explicit import + one explicit call, never a dynamic registry/plugin-discovery mechanism; (4)
if the job needs tunable retry/concurrency, add job-prefixed fields to both `Settings` and
`AppConfigFile` rather than a generic per-type dict, since `register_job()` takes them as
explicit keyword args and has no config-file dependency of its own. Tests mirror the split:
`tests/scheduling/` covers the generic `register_job`/`with_retry` helpers with dummy
functions/queues; `tests/media_library/test_jobs.py` covers the slice-specific wiring.
