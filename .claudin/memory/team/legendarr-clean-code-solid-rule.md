---
name: legendarr Clean Code & SOLID rule
description: Where the Clean Code/SOLID project rule lives and what was refactored to comply with it, added 2026-07-16
type: project
---

Added `.claudin/rules/clean-code-solid.md` (scoped to `modules/**/*.py` via `paths`) covering
SRP/OCP/LSP/ISP/DIP and general clean-code guidance tailored to this repo's Screaming
Architecture + Vertical Slice layout.

Ran an analysis against it and applied the clear-cut, low-risk fixes (codebase was only
~430 lines at the time, so most "violations" were structural precursors, not full anti-patterns):

- `modules/backend/src/legendarr_backend/media_library/providers/base.py` (`media_providers/`
  renamed to `media_library/providers/` in the 2026-07-16 domain-driven-slices reorg, see
  `legendarr-architecture.md`) — `MediaItem` dataclass
  + `MediaLibraryClient` Protocol (`list_items()`, `close()`) shared by `RadarrClient` and
  `SonarrClient`, which previously had no common contract despite being structurally identical
  (`MediaFile`/`SeriesFile` duplicated dataclasses, `list_movies()`/`list_series()` diverging
  method names). `list_movies`/`list_series` were renamed to `list_items` on both clients.
- `sync_media_library.py` — superseded 2026-07-20 (PR #12): it now takes a DB `Session`
  and iterates enabled `ArrService` rows, building a client per connection via
  `client_factory.build_client` (widened to accept the `ArrService` model, not just
  `ArrServiceInput`). The old `radarr`/`sonarr` params and
  `bootstrap.py::_build_media_clients` are gone — the composition root no longer
  constructs media clients at all.
- `modules/web/.../media_library/router.py` — added a `# TODO` on the hard-coded empty
  `{"movies": [], "series": []}` stub so it isn't mistaken for finished behavior.

Deliberately **not** changed (would be over-engineering or would fight existing, documented
decisions):
- `database/engine.py`'s manual `_engine` global cache — tests
  (`test_database.py`, `test_router.py`) monkeypatch `database._engine` directly; see
  `legendarr-db-migrations.md` for the documented caching gotcha. Switching to `@lru_cache`
  would require rewriting those tests for a cosmetic consistency gain.
- Duplicated `Settings`/`WebSettings` boilerplate between `legendarr_backend` and `legendarr_web`
  — intentional per `legendarr-architecture.md`: web no longer imports the backend package at
  all as of the 2026-07-16 split, so a shared base class isn't available without reintroducing
  that dependency.

**Why:** avoids re-litigating the same trade-offs (which "violations" are real vs. deliberate)
next time someone runs a SOLID pass on this codebase.

**How to apply:** re-run the same read-only analysis (Explore agent) after a growth spurt (new
slice, new provider) rather than assuming these are the only gaps — the report above was
explicitly scoped to what existed on 2026-07-16.
