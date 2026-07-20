---
name: legendarr media-library deferred follow-ups
description: Items deliberately deferred from PR #12 validation (2026-07-20) — Windows path mapping, DB-level cascade to replace manual media cleanup, minor form gaps
type: project
---

Deferred after PR #12 (media persistence + per-connection path mapping, validated 2026-07-20):

1. `resolve_local_path` only handles `/` separators — Windows-style paths (`C:\Movies\...`) don't match prefix boundaries and pass through untranslated; a remote prefix of `/` silently disables mapping. Recorded as a known gap in ROADMAP.md.
2. Architecture audit flagged the manual Movie/Series cleanup in `manage_arr_service.delete_arr_service` as a *reverse* slice dependency (arr_services → media_library), making the two slices conceptually bidirectional. Recommended fix: `ondelete="CASCADE"` on the FK + `PRAGMA foreign_keys=ON` in `database/engine.py`, restoring unidirectionality (media_library → arr_services only). No circular import exists today; not scheduled.
3. The connection update form has no "blank = keep" rule for `remote_path_prefix`/`local_path_prefix` (unlike api_key) — a POST from a cached pre-deploy page would clear existing mappings. Low likelihood.
4. Editing a connection's mapping via the UI requires the server to be reachable (probe-on-PUT inherited from PR #10), so mappings can't be edited while the arr server is down.

**Why:** user triaged PR #12 review findings — fixed the high-severity sync-commit-scope bug and the orphan-media bug, explicitly deferred the rest ("o #3 deixa pra depois").

**How to apply:** if touching `delete_arr_service` or `database/engine.py`, prefer implementing #2 over adding more manual cleanup; #1 becomes relevant if a Windows-host Radarr/Sonarr user appears; treat #3/#4 as known UX gaps, not regressions.
