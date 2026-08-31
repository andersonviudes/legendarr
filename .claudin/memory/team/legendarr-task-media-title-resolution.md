---
name: legendarr-task-media-title-resolution
description: Tasks page shows media titles instead of raw job_ids — resolved at display time in system/, not by threading a Session through every enqueue_* call
type: project
---

Built 2026-08-31 on branch `feat/system-task-media-titles` (PR #109), prompted by the user
looking at the live queue and being unable to tell whether two concurrent `ffmpeg` processes
were the same file twice (a bug) or two different episodes (expected — see
[[legendarr-prod-deployment-topology]]'s earlier `scan` queue report from the same day). Every
`enqueue_*` job in every slice (`subtitle_discovery`, `subtitle_acquisition`,
`subtitle_translation`, `subtitle_timing_sync`, `media_library`, `media_metadata`) calls
`scheduler.add_job(..., name=job_id, ...)`, so the System > Tasks page, the topbar
notification panel, and the dashboard's live-activity widget all rendered a bare id like
`subtitle_scan:63` — no indication of which file that actually was.

**What exists:** `legendarr_backend.system.resolve_job_media_title.resolve_job_media_titles(session,
job_ids)` parses each `job_id`'s known prefix (`subtitle_scan`/`subtitle_acquisition`/
`subtitle_translation` → `MediaFile`, `subtitle_timing_sync` → `Subtitle` → `MediaFile`,
`pending_subtitle_reconcile` → `Series`, `media_scan`/`media_metadata_fetch` →
`Movie`/`Series` by kind) and batch-resolves it to a title via the new
`media_library.locate.resolve_media_file_display_name` (movie title, or `"{series title} —
{filename}"`). A `job_id` with an unrecognized prefix (a periodic fan-out's own id, e.g.
`subtitle_discovery_scan_fanout` — already readable on its own) or naming media deleted since
is simply absent from the result, so the caller falls back to the raw `job_id`/`job.name`.
Wired into both `GET /system/tasks/running` (`system/running_tasks.py::list_running_tasks`,
now takes a `Session`) and `GET /system/jobs/history` (resolved inline in
`system/router.py::get_job_history`) — one fix covers the queue, the topbar panel, the
dashboard widget, and job history at once, since they all render the same `task.name`/
`run.name` field and `legendarr_web` just proxies the JSON through with zero template changes
(confirms `AGENTS.md`'s "web never imports legendarr_backend" boundary held cleanly here).

**Why resolve at display time instead of at enqueue time:** the obvious-looking alternative —
pass a `Session` into every `enqueue_subtitle_scan`/`enqueue_translation`/`enqueue_acquisition`/
etc. and set `name=` to the real title when `add_job` is called — was rejected after tracing
every call site. Several `enqueue_*` functions are invoked from places with no session in easy
reach at that exact frame (an `OnCascade`/`OnReconcilePending` callback typed as
`Callable[[int], None]`, wired via `app.state` from `legendarr_bootstrap` specifically so
`media_library` doesn't have to import `subtitle_discovery` — see
[[legendarr-scheduling-job-conventions]]), and two existing unit tests
(`test_enqueue_subtitle_scan_adds_adhoc_job_with_event_safe_policy` and its dedupe sibling)
call `enqueue_subtitle_scan` directly with no DB fixture at all, monkeypatching `add_job`
itself — opening a real `get_session()` inside the enqueue function would have hit the lazily-
created global engine with no migrated schema and raised `OperationalError: no such table`.
Resolving from `job_id` at display time instead touches only the `system` slice (plus one new
`media_library.locate` helper) — zero signature changes to any `enqueue_*` function, zero risk
to the existing enqueue-level tests.

**How to apply:** a new per-item job type needs a `job_id` format `resolve_job_media_titles`
doesn't parse yet (adding a prefix to one of its 4 dicts + a batch query) if it should show a
title on the Tasks page instead of its raw id — everything else about the job's own
`jobs.py` wiring is unaffected.
