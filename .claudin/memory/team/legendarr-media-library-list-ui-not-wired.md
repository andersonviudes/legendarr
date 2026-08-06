---
name: legendarr media-library list UI not wired
description: RESOLVED 2026-08-01 by PR #25 — /media/series and /media/movies now call the real backend list API
type: project
---

**RESOLVED 2026-08-01 on PR #25 (`e15bac0`, "capture arr metadata and list movies/series in the
UI").** `show_series`/`show_movies` in
`modules/web/src/legendarr_web/media_library/router.py` now call `service.list_series`/
`service.list_movies` against the real backend API and render actual synced data — confirmed
2026-08-06 while working on the detail-page translate button (both `/media/series/{id}` and the
list pages render real Sonarr-synced data, e.g. "Ahsoka", against the dev Sonarr stack). The
history below (hardcoded empty lists, no backend GET endpoint) describes the pre-PR-#25 state
and no longer applies to current code.

Original finding, kept for context: `show_series`/`show_movies` used to render their templates
with a hardcoded `{"series": []}` / `{"movies": []}`, never calling any backend API, and there
was no GET endpoint in `legendarr_backend`'s media_library router
(`modules/backend/src/legendarr_backend/media_library/router.py`) to list synced movies/series —
only `POST /media/scan` existed. The "0 series synced" / "Nothing synced yet" message was
permanent regardless of how many successful library syncs ran; it wasn't a signal that sync
failed.

Confirmed 2026-08-01 while testing the Sonarr dev stack (`docker-compose.dev.yml`): after adding
a Sonarr connection and forcing a library sync, `SELECT * FROM series` in
`/config/legendarr.db` inside the `legendarr` container showed both series correctly persisted
(title, remote_path, arr_service_id) — the sync job itself works fine end-to-end. The `/media/series`
page still said "0 series synced" because the route never queries that data.

Related: the library sync job (`media_library/jobs.py::register_sync_job`) has no manual
"run now" trigger anywhere (backend API, CLI, or UI) — first run fires only after a full
interval from scheduler start (default 15 min via Tasks settings). To force a near-immediate
sync for manual testing, temporarily drop the Library sync interval to 1 minute in
Settings → Tasks and save (per the page's own note, saving restarts the interval countdown);
restore it afterward.

**Why:** this is exactly the kind of "did my test setup work" question a dev testing Sonarr sync
will hit and misdiagnose as a scheduler/connection problem when it's actually a missing read path
in the web UI.

**How to apply:** no longer actionable — kept only as history for why the list pages once showed
"0 series synced" regardless of sync success. See [[legendarr-roadmap-basis]] for the current
0.3.0 scope and known gaps on the media-library slice (e.g. the translate-button validation gap
recorded 2026-08-06).
