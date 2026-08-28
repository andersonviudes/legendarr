---
name: legendarr history slice
description: History view (ROADMAP 0.20.0) — TranslationFailure/AcquisitionFailure tables + history/ slice, merging successes and failures into one feed
type: project
---

Built 2026-08-28 on `feat/dashboard-history`, closing ROADMAP.md 0.20.0's last "Operations"
item ("Translation/acquisition history and error status"), a sibling of
[[legendarr-statistics-slice]] but distinct: Statistics aggregates counts/trends from
**successful** attempts only; History is a raw, per-attempt feed that also needs failures,
which nothing persisted before this.

**Gap found during planning**: `TranslationAttempt`/`AcquisitionAttempt` are explicitly
append-only audit trails of successful outcomes only. Both `translate_media_file.py`'s
`_translate_with_fallback` and `acquire_media_file_subtitle.py`'s `_search_and_download`
already catch every provider's exception in an identical per-provider try/except-log-continue
shape, but on full chain exhaustion they only logged — nothing queryable was ever recorded.
`system/job_history.py`'s `JobRun` doesn't cover this either: each per-media-file
translate/acquire run is its own APScheduler job, but both functions swallow provider errors
internally and return a skip result rather than raising, so the job function itself never
fails and `JobRun` never sees it.

**Design decision**: added two new failure-only tables — `TranslationFailure`
(`subtitle_translation/models.py`) and `AcquisitionFailure` (`subtitle_acquisition/models.py`)
— keyed by `media_file_id` (not `subtitle_id`, unlike the Attempt tables: a failure never
produces a target `Subtitle` row to point at). Deliberately **not** added as new
nullable columns on the existing Attempt tables, to keep `compute_statistics.py`'s
"every row is a win" assumption untouched. A failure row is recorded only when the provider
loop is **fully exhausted with at least one real exception** — a clean "nothing found, zero
exceptions" pass (translation has none by construction; acquisition's `no_match_found` skip
reason) stays a non-error, same posture as every other `skipped_reason`.

**Backend shape**: new `history/` slice (`list_history.py`, `schemas.py`, `router.py`), one
route `GET /history?limit=50`. `list_history` fetches each of the four source tables
newest-first and capped at `limit` *before* merging (bounded query cost regardless of table
growth — unlike `compute_statistics`, which must fetch everything for its 30-day window),
resolves `subtitle_id → media_file_id` via one batched `Subtitle` lookup, then resolves
`media_file_id → title` via `Movie`/`Series` — a series entry's title is `Series.title` plus
the file's own filename (e.g. "Breaking Bad — S02E05.mkv"), not a live per-episode Sonarr
fetch (too expensive per history row, see `get_media_detail._episode_reads`).

**Web shape**: filled in a `/history/` page stub that had existed since before the module
rename to `src/` (`d6c5a60`) — nav link, router, empty-state template were already wired,
just never built out. Reused `task-line-list`/`task-line-status--{status}` CSS and
`system.tasks.status_success`/`status_failure` i18n keys from the System → Tasks page instead
of inventing parallel ones — same list-of-rows-with-a-status-pill shape.

**Why:** avoids re-discovering that neither slice persists a failure anywhere (easy to assume
`JobRun` covers it — it doesn't, see above), and the "two failure tables, not nullable columns
on the win tables" tradeoff if a future change wants to add failure detail (e.g. an HTTP
status code) without touching Statistics' semantics.

**How to apply:** any future write to `TranslationFailure`/`AcquisitionFailure` should go
through `translation_history.record_translation_failure`/`audit_trail.record_acquisition_failure`,
not a raw `session.add(...)`, and should only fire on an actual caught exception, never on a
"nothing to do" skip reason — same rule this feature followed for what counts as an error.
