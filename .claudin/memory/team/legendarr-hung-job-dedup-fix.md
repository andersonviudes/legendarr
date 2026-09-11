---
name: legendarr-hung-job-dedup-fix
description: PR #128 — a stuck speech-to-text thread wedged acquire_bulk forever and caused duplicate Queued entries; fixed with an abandoned-daemon-thread timeout + is_task_active() dedup on every ad-hoc enqueue_*
type: project
---

Fixed 2026-09-09 (branch `fix/live-activity-stuck-acquire-bulk`, PR #128, commit `22ff9c6`).
A speech-to-text transcription (`audio_transcription/transcribe_audio.py`) that ran past its
`speech_to_text_timeout_seconds` budget left its worker thread alive forever —
`ThreadPoolExecutor.__exit__`/shutdown blocks waiting for every submitted task to finish, so a
single hung transcription permanently occupied both `ACQUIRE_BULK` slots. Because acquisition's
periodic fan-out re-enqueues eligible media files every cycle via `add_job(...,
replace_existing=True)`, and the hung job had already left the jobstore for the executor by
then, the plain jobstore-level dedupe never caught it — every cycle added a fresh duplicate
"Queued" entry for the same file, showing up as unbounded Live Activity growth.

**Two-part fix:**
1. `_transcribe_with_timeout` (`transcribe_audio.py`) now runs the transcription on a
   `daemon=True` thread and does a single `thread.join(timeout=...)` — if it's still alive
   after that, the function returns `[]` and logs a warning, abandoning the thread instead of
   waiting on it again. The daemon flag also means it can't block process shutdown.
2. New `RunningTaskRegistry.is_active(job_id)` / module-level `is_task_active(job_id)`
   (`scheduling/running_tasks.py`) — true if `job_id` is already dispatched to an executor
   (genuinely running, or still queued behind other same-queue work), which is exactly the
   state a plain `replace_existing` jobstore dedupe misses once a job has left the jobstore for
   its executor. Every ad-hoc per-item `enqueue_*` across every slice (`media_library`,
   `media_metadata`, `subtitle_acquisition/jobs.py` + `upgrade_jobs.py`, `subtitle_discovery`,
   `subtitle_timing_sync`, `subtitle_translation`) now checks `is_task_active(job_id)` before
   calling `add_job` and skips re-enqueuing when it's already in flight.

**Why it matters:** this is now the standard shape for any *new* ad-hoc per-item job — see
[[legendarr-scheduling-job-conventions]] for the general enqueue pattern this extends. A
hung/slow job of any kind (not just transcription) can no longer wedge a whole bulk queue's
capacity or multiply itself in the Tasks/Live Activity view on every fan-out cycle.

**How to apply:** any new per-item `enqueue_*` added to a slice should call
`is_task_active(job_id)` and skip re-enqueuing if it returns `True`, exactly like the call
sites this PR touched. Any new job that runs arbitrary-duration external work (subprocess,
model inference, a network call with no built-in timeout) should bound it with an
abandoned-daemon-thread timeout like `_transcribe_with_timeout`, not a bare blocking call.

**Extended 2026-09-11:** never fan work out with `with ThreadPoolExecutor(...) as executor:` in
a job path either — `__exit__` is `shutdown(wait=True)`, so one stuck worker thread wedges the
job permanently, and the pool's non-daemon threads block interpreter shutdown on top of it. Use
the `Thread(daemon=True)` + shared-deadline `join()` shape `subtitle_acquisition/
provider_search.py`'s `_search_all` now uses. See [[legendarr-opensubtitles-hash-hang-fix]] for
the full chain of call sites this pattern has had to be applied to.
