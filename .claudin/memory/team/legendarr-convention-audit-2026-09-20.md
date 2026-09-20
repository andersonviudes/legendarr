---
name: legendarr-convention-audit-2026-09-20
description: Full convention-adherence audit of 2026-09-20 — all project conventions verified clean, two minor known gaps (web config/backend_client test dirs; poster raw httpx re-confirmed deliberate)
type: project
---

Full read-only convention audit run 2026-09-20 on `main` (version v0.22.12-era, ~50d8e6d):
`make lint` clean (610 files formatted), `make test` green (1729 tests), and a
multi-category check of the rules in `.claudin/rules/` + AGENTS.md against the tree.

**Verified clean (don't re-audit from scratch next time — start from this):**
- All ~24 backend slices mirror their `src/backend/tests/` counterparts 1:1; zero
  `legendarr_backend` imports in `src/web` (cross-slice constants are deliberately
  duplicated with comments saying so, e.g. `history/router.py`).
- Every outbound provider HTTP call goes through `ProviderHttpClient`; all `add_job`
  calls live in `scheduling/` + per-slice `jobs.py`, registered in
  `bootstrap.build_scheduler()`; all 23 `table=True` models have matching Alembic
  revisions (no schema drift); `configure_logging()` called exactly once in
  `legendarr_bootstrap/app.py`; last 30 commits all follow `type(scope): lowercase`
  with slice-named scopes; zero TODO/FIXME in `src/`.

**Two gaps found (both minor, both still open):**
1. `src/web`'s `config/` and `backend_client/` are the only source folders with no
   corresponding `src/web/tests/` dirs — the tests-mirror-slices rule is followed
   everywhere else.
2. `media_metadata/fetch_metadata.py`'s poster download uses raw `httpx.get` — this
   looks like a violation but is a **documented deliberate decision** (see
   [[legendarr-media-metadata-slice]]: `ProviderHttpClient` models one fixed
   `base_url` per provider, not a one-off arbitrary-CDN download). Re-flagged by the
   audit; still deliberate, not something to "fix".

Also note: the shared team memory list contains stale/resolved entries (e.g.
[[legendarr-echo-translation-provider-not-wired]] was re-verified and is still true,
not fixed). Prune the index when those get resolved for real.

**Why:** a full audit is ~40 tool calls; recording the pass rate means the next audit
can diff against this snapshot instead of redoing every category.

**How to apply:** when someone asks "is anything out of the project's pattern?",
spot-check the two open gaps above and anything changed since 2026-09-20, rather than
re-running all categories.
