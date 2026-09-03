---
name: legendarr-bulk-queue-worker-default-mismatch
description: PR #119's cpu_scaled_workers() defaults never reach the real scheduler; bulk queues run at 1 worker unless env-overridden
type: project
---

PR #119 (`b1f66a5`) added `cpu_scaled_workers()` in
`src/backend/src/legendarr_backend/scheduling/queues.py:50-58` and used it as the
`QUEUE_WORKERS` dict default for `TRANSLATE_BULK`/`ACQUIRE_BULK`/`METADATA_BULK`/`UPGRADE_BULK`
(`queues.py:61-73`). But the real runtime path never reads that default: `bootstrap.py`'s
`build_scheduler()` (`src/backend/src/legendarr_backend/bootstrap.py:32-46`) always builds a
*fully populated* `queue_workers` dict from `AppConfigFile` (`config/settings.py:181-191`), and
those `Settings` fields still hardcode `default=1` (stale — the comment above them at
`settings.py:180` claims they "mirror `scheduling.queues.QUEUE_WORKERS`", which stopped being
true when PR #119 landed).

`build_bare_scheduler()` (`scheduling/scheduler.py:30-34`) does `workers.get(queue, default)`
where `default` comes from `QUEUE_WORKERS` — but since bootstrap's dict always has every key
present, `.get` never falls through to the CPU-scaled default. Only callers passing a *partial*
dict (tests) ever see `cpu_scaled_workers()` in practice.

Net effect: on a fresh install / any host that hasn't manually set
`LEGENDARR_TRANSLATE_BULK_QUEUE_WORKERS` etc., every bulk queue (translate, acquire, metadata,
upgrade, scan_bulk) runs at concurrency 1 — items are processed one at a time regardless of
host CPU count, exactly as if PR #119 never happened. Discovered 2026-09-02 while comparing
job/scheduler design against Bazarr (`../bazarr`) for speed insights.

**Fix direction (not yet applied):** either drop the `default=1` literals in `settings.py` in
favor of `default_factory` pulling from `QUEUE_WORKERS[...]` per field, or have
`build_scheduler()` omit a config field from the dict it passes when it hasn't been explicitly
overridden (distinguishing "user set it to 1" from "field defaulted to 1") so the `.get(queue,
default)` fallback in `scheduler.py` actually engages.
