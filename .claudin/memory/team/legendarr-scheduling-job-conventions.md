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

**Update (2026-09-02) — split a combined job into two independent ones (acquisition vs.
upgrade):** `subtitle_acquisition/jobs.py`'s periodic fan-out used to do two things per
media file back-to-back: search for a missing subtitle, and — as a fallback when nothing
was missing — re-search providers for a better-scoring release of one already acquired
("upgrade/replace", ROADMAP 0.12.0), throttled by a per-file timestamp
(`acquisition_upgrade_recheck_hours`). Per a user request to run these on separate
schedules (acquisition unchanged, upgrade daily), upgrade was pulled out into its own
slice-owned job module (`subtitle_acquisition/upgrade_jobs.py::register_subtitle_upgrade_job`,
job id `subtitle_upgrade_fanout`), its own queue (`JobQueue.UPGRADE_BULK`), and its own
config block (`upgrade_interval_minutes` default 1440/24h, `upgrade_retry_attempts`,
`upgrade_retry_delay_seconds`, `upgrade_max_instances`, `upgrade_coalesce`,
`upgrade_bulk_queue_workers`) — `acquisition_upgrade_recheck_hours` was removed, replaced
by `upgrade_interval_minutes` doing double duty as both the job's own APScheduler interval
and the `should_check_for_upgrade` throttle window passed into it. The two jobs share one
small helper (`subtitle_acquisition.jobs.media_file_ids_with_completed_scan`) for the
"every discovery-scanned `MediaFile`" eligibility walk, otherwise fully independent.
**Behavior change users should know about:** upgrade checking used to also fire immediately
(unthrottled) on every manual/event-triggered acquisition — the "Search Subtitles" button,
the discovery-scan cascade, and translation's missing-source-subtitle cascade — because
none of those callers passed a real throttle. That immediate side effect is gone; upgrade
now only ever runs from `subtitle_upgrade_fanout`, at most once a day by default. Confirmed
with the user as the desired trade-off for a simpler two-job mental model.

**Update (2026-09-02, later same day) — score-aware, threshold-gated upgrade
prioritization:** built directly on the split above. `should_check_for_upgrade` was
replaced by `upgrade_search_priority(session, media_file, recheck_after) -> float | None`
in `upgrade_media_file_subtitle.py` — one function now doing eligibility (has profile,
has an `AcquiredSubtitle`), a new score-threshold gate
(`LanguageProfile.movie_upgrade_threshold`/`series_upgrade_threshold`, int 0-100, default
100 so existing profiles keep today's "always eligible" behavior), and the recheck-window
throttle all at once — returning the current subtitle's score (not just a bool) so it can
double as a sort key. `upgrade_jobs.py::enqueue_full_upgrade_scan` now calls this for
every discovery-scanned media file, keeps only the ones it returns a score for, and
enqueues them **ascending by score** so the worst-scoring subtitles reach the (typically
single-worker) `UPGRADE_BULK` queue first — previously it enqueued every scanned media
file unconditionally and let `run_upgrade` skip no-ops at execution time. Also
**decoupled the recheck window from the run interval**: a new `upgrade_recheck_minutes`
config field (default 4320 = 3 days, config/env-only like `upgrade_interval_minutes`
itself, no Settings UI) replaces `upgrade_interval_minutes` as the throttle passed into
`upgrade_search_priority` — before this the fan-out's own cadence and the per-file
recheck window were the same number by construction. See
[[legendarr-match-score-configurable]] for the sibling field pair this was modeled on.

**Update (2026-08-31) — each queue's thread-pool size is now config-driven too:**
`scheduling/queues.py`'s `QUEUE_WORKERS` dict is still the *default* worker count per
`JobQueue` (used when a caller passes nothing), but it's no longer the sole source of
truth. `Settings`/`AppConfigFile` gained one `<queue>_queue_workers` field per `JobQueue`
member (`scan_queue_workers`, `scan_bulk_queue_workers`, `translate_queue_workers`, ...);
`legendarr_backend.bootstrap.build_scheduler()` builds a `dict[JobQueue, int]` from them
and passes it to *both* `scheduling.scheduler.build_scheduler(queue_workers)` (sizes each
`ThreadPoolExecutor`) and `scheduling.running_tasks.attach_running_task_registry(scheduler,
queue_workers)` (so the Tasks page's "queued" badge — see [[legendarr-prod-deployment-topology]]
for the real-world report that motivated this — uses the *actual* configured capacity, not
the `QUEUE_WORKERS` default, via `RunningTaskRegistry.configure()`). Same posture as most
other scheduling knobs: config/env-only, no Settings UI yet — and unlike `max_instances`/
`coalesce`/interval fields, these also need a full process restart, since the executor pool
is sized once at `build_scheduler()` time and never rebuilt when `config.yaml` changes.
