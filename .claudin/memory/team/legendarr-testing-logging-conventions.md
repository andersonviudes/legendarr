---
name: legendarr testing conventions & logging conventions
description: Shared test fixtures per module (conftest.py) and how logging is configured/used across legendarr backend/web/bootstrap
type: project
---

Built 2026-07-16 on branch `feat/testing-logging-conventions`, completing the last `ROADMAP.md`
0.1.0 bullet ("Shared testing conventions ... and structured logging conventions").

**Testing — what exists:** each module's own `tests/conftest.py` holds fixtures shared across
that module's slices (fixtures are not shared *across* modules — backend/web/bootstrap are
separate `uv` packages). `modules/backend/tests/conftest.py` (new) has three fixtures:
`_isolated_data_dir` (autouse, session-scoped — sets `LEGENDARR_DATA_DIR` to a temp dir, same
fixture already used verbatim in `modules/web/tests/conftest.py` and
`modules/bootstrap/tests/conftest.py`; kept duplicated across the three module test trees on
purpose — no shared test-utils package exists, and building one for a 5-line fixture isn't
worth it), `isolated_database(tmp_path, monkeypatch)` (points `database.engine`'s module-level
singleton at a fresh on-disk SQLite DB under `tmp_path` for tests that go through the real
`init_db()`/Alembic path — used by `tests/database/test_database.py` and
`tests/language_profiles/test_router.py`), and `in_memory_session()` (yields a `Session` bound
to `create_engine("sqlite://")` + `SQLModel.metadata.create_all(engine)`, bypassing Alembic
entirely, for tests that only need a working `Session` against the current schema — used by
`tests/language_profiles/test_manage_language_profile.py`). `modules/web/tests/conftest.py`
also gained `stub_backend_client(app, handler=...)`, a fixture factory that wires
`app.dependency_overrides[get_backend_client]` to an `httpx.MockTransport`, defaulting to an
empty-profiles-list handler — used by `tests/dashboard/test_dashboard.py` and
`tests/language_profiles/test_settings_page.py`.

**Logging — what exists:** `configure_logging()` (`legendarr_backend/logging/setup.py`) is
called exactly once, in `legendarr_bootstrap/__main__.py::main()` before `uvicorn.run(...)` —
this is the real entrypoint for both `make run` and the Docker `CMD` (`python -m
legendarr_bootstrap`). Every module that logs gets its own `logger =
logging.getLogger(__name__)` at the top of the file (already the organic pattern in
`scheduling/retry.py`/`media_library/jobs.py` before this work; now documented in
`.claudin/rules/python-conventions.md`). No structured/JSON logging, no correlation IDs, no
configurable log level — `configure_logging()` stays hardcoded at `INFO`, per explicit YAGNI
call: nothing in the roadmap needs machine-parseable logs or runtime log-level control yet.

**Why:** before this, `configure_logging()` was only ever called from
`legendarr_backend/__main__.py`, which `make run`/Docker never actually invoke (they run
`legendarr_bootstrap`, not `legendarr_backend`, directly) — so in the real running app the root
logger was never configured, and every existing `logger.info(...)`/`logger.warning(...)` call
was silently dropped (default root logger only surfaces WARNING+, unformatted). Confirmed via
`Makefile:17` (`run: uv run --package legendarr-bootstrap python -m legendarr_bootstrap`) and
`Dockerfile:34` (`CMD ["python", "-m", "legendarr_bootstrap"]`), both landing in
`legendarr_bootstrap/__main__.py`. `legendarr_backend/__main__.py` itself is an intentional
standalone entrypoint (confirmed with the user) and was left untouched — it's a separate,
narrower way to run just the backend's scheduler without the web UI, not dead code.

The DB-isolation fixture extraction reused two real, already-duplicated 3-line blocks (not
speculative) — `Settings(data_dir=tmp_path, database_url="")` +
`monkeypatch.setattr(database, "get_settings", ...)` + `monkeypatch.setattr(database, "_engine",
None)` — found identical in `test_database.py` and `test_router.py`. The in-memory-session
fixture had only one call site at the time (`test_manage_language_profile.py`), but was
extracted anyway per explicit user confirmation: 0.2.0 (`ROADMAP.md`) adds `LanguageProfile`
`update`/`delete` and a translation orchestrator, both needing the same Session-against-schema
pattern immediately — same "formalize ahead of the next milestone" reasoning as the scheduling
conventions work ahead of 0.9.0.

**How to apply:** when adding a backend test that needs an isolated real DB (API tests, `init_db()`
tests), use the `isolated_database` fixture instead of hand-rolling the monkeypatch dance. When a
test only needs a `Session` against the current schema (service-function tests), use
`in_memory_session`. When adding a web test that needs to stub the backend HTTP client, use
`stub_backend_client(app, handler=...)` instead of duplicating the `MockTransport`/
`dependency_overrides` wiring. When adding logging to new code, add `logger =
logging.getLogger(__name__)` at module top — never call `configure_logging()` again outside
`legendarr_bootstrap/__main__.py`.
