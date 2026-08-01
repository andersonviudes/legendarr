---
name: legendarr media-library list UI not wired
description: /media/series and /media/movies web pages are hardcoded stubs — sync works but never shows there
type: project
---

`modules/web/src/legendarr_web/media_library/router.py` — `show_series`/`show_movies` render
their templates with a hardcoded `{"series": []}` / `{"movies": []}`, never calling any backend
API. There is also no GET endpoint in `legendarr_backend`'s media_library router
(`modules/backend/src/legendarr_backend/media_library/router.py`) to list synced movies/series —
only `POST /media/scan` exists. So the "0 series synced" / "Nothing synced yet" message on those
pages is permanent regardless of how many successful library syncs run; it's not a signal that
sync failed.

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

**How to apply:** when the roadmap reaches building out the Series/Movies library browsing pages,
this is the starting point — add a list endpoint to the backend's media_library router and wire
`show_series`/`show_movies` to call it instead of passing an empty list.
