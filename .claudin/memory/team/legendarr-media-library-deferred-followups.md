---
name: legendarr media-library deferred follow-ups
description: Items deliberately deferred from PR #12 validation (2026-07-20) — Windows path mapping, minor form gaps. DB-cascade item (#2) was resolved 2026-07-20 on feat/language-profile-crud.
type: project
---

Deferred after PR #12 (media persistence + per-connection path mapping, validated 2026-07-20):

1. `resolve_local_path` only handles `/` separators — Windows-style paths (`C:\Movies\...`) don't match prefix boundaries and pass through untranslated; a remote prefix of `/` silently disables mapping. Recorded as a known gap in ROADMAP.md.
2. ~~Architecture audit flagged the manual Movie/Series cleanup in `manage_arr_service.delete_arr_service` as a *reverse* slice dependency~~ — **RESOLVED 2026-07-20** on `feat/language-profile-crud`. `Movie.arr_service_id` now has `ondelete="CASCADE"`, `Movie.language_profile_id`/`Series.language_profile_id` have `ondelete="SET NULL"` (migration `3605a01d1781`), and `database/engine.py::get_engine()` enables `PRAGMA foreign_keys=ON` per-connection for SQLite (also added to the `in_memory_session` test fixture in `modules/backend/tests/conftest.py` — it builds its own engine, so it needed the same listener). The manual cleanup loops in `delete_arr_service` and `delete_language_profile` were removed; both `arr_services` and `language_profiles` no longer import `media_library.models` at all, restoring unidirectionality (`media_library` → `{arr_services,language_profiles}` only).
3. The connection update form has no "blank = keep" rule for `remote_path_prefix`/`local_path_prefix` (unlike api_key) — a POST from a cached pre-deploy page would clear existing mappings. Low likelihood.
4. Editing a connection's mapping via the UI requires the server to be reachable (probe-on-PUT inherited from PR #10), so mappings can't be edited while the arr server is down.

**Why:** user triaged PR #12 review findings — fixed the high-severity sync-commit-scope bug and the orphan-media bug, explicitly deferred the rest ("o #3 deixa pra depois"). Item #2 came back up in a 3-agent standards/architecture review of `feat/language-profile-crud` (2026-07-20) — the new `language_profiles` slice had reproduced the exact same manual-cleanup pattern for its own FK to `media_library`, and the user asked to fix it then.

**How to apply:** #1 becomes relevant if a Windows-host Radarr/Sonarr user appears; treat #3/#4 as known UX gaps, not regressions. If a *new* slice ever needs to react to a row being deleted in another slice, prefer a DB-level FK `ondelete` clause over hand-rolled cleanup — SQLite needs `PRAGMA foreign_keys=ON` enabled per-connection for it to actually fire (raw `create_engine()` calls, like test fixtures, must attach `database.engine.enable_sqlite_foreign_keys` themselves; only `get_engine()` does it automatically).
