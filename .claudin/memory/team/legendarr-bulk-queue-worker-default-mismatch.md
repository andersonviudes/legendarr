---
name: legendarr-bulk-queue-worker-default-mismatch
description: Fixed in code by PR #120, but any pre-existing data/config.yaml stays pinned at the old value forever — no migration
type: project
---

**PR #120 (`42d536f`, "fix dead bulk queue worker defaults, cap concurrency at 4"), already on
`main`,** made `settings.py`'s `*_queue_workers` fields use
`default_factory=lambda: QUEUE_WORKERS[JobQueue.X]` instead of hardcoded `default=1` literals,
so `cpu_scaled_workers()` (`queues.py:50-60`, capped at 4) reaches `build_scheduler()` for a
*fresh* install. Confirmed by reading `config/settings.py:186-214`, `config/config_file.py:114-
141`, and `bootstrap.py:32-44`.

**But this does NOT self-heal an existing install.** `load_or_create_config_file()`
(`config/config_file.py:145-250`) does `merged = {**defaults, **data}` where `data` is whatever
is already on disk at `data_dir/config.yaml` — any key already present there always wins over
the current code default, permanently, with no version check or migration. So an install whose
`config.yaml` was written before PR #120 (when the default was still the literal `1`) has
`acquire_bulk_queue_workers: 1` (and `scan_bulk_/translate_bulk_/metadata_bulk_/
upgrade_bulk_queue_workers: 1`) baked into the file forever — upgrading legendarr does nothing
for it. Confirmed 2026-09-03: this repo's own dev instance (`data/config.yaml`) was still stuck
at `acquire_bulk_queue_workers: 1` despite running code that post-dates PR #120; every bulk-fan-
out task in the Tasks page ran one-at-a-time ("Queued") because of it. Manually bumping the line
in `config.yaml` and restarting the process is the only fix — there's no UI field or migration
for these (see `settings.py:175-185`: config-file/env-only, needs a full restart since
`build_scheduler()` sizes the `ThreadPoolExecutor` once at startup).

**Still open:** a version-aware migration (or at least a startup log warning) that detects a
`*_queue_workers` value still sitting at the pre-PR#120 default and offers to bump it. Original
mismatch description (why the code-level bug existed pre-#120) kept below for history.

**Follow-up (2026-09-03, PR TBD):** while investigating this, lowered `cpu_scaled_workers()`'s
default `maximum` from 4 to 2 (`queues.py`) — `PROVIDER_MAX_CONCURRENCY` already caps any one
provider at 3 concurrent calls, so 4 bulk-queue workers all hitting different providers wasn't
buying much beyond 2, and 2 is friendlier to a modest host. Also raised `SYNC`/`SCAN_BULK`/
`MAINTENANCE` from their flat `1` to `2` — those were never part of the `cpu_scaled_workers()`
group and so never benefited from PR #119/#120 at all. `SCAN_BULK` stays deliberately below the
CPU-scaled queues (still I/O-throttled for network-mount scans), just at 2 instead of 1 now. The
"existing config.yaml never picks up a new code default" gap above still applies to *this*
change too — an install upgrading past it needs the same manual `config.yaml` bump.



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
