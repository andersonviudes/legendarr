---
name: legendarr-alembic-filecfg-logging-gotcha
description: RESOLVED 2026-08-27 — Alembic's env.py fileConfig() used to silently wipe the app's logging setup (stdout + System page ring buffer) every startup; now skipped for the programmatic init_db() path
type: project
---

`src/backend/db/migrations/env.py` calls `fileConfig(config.config_file_name)` (stdlib
`logging.config.fileConfig`) to set up logging from `alembic.ini`. This didn't just break
pytest's `caplog` (the original finding below) — it also broke the *running app*: every
call to `init_db()` (real startup, both entrypoints, plus every test using
`isolated_database`) ran Alembic migrations, which reconfigured the **root logger** to
`alembic.ini`'s own setup (stderr, WARNING-only) and disabled every already-imported
module logger process-wide. Symptom: the System → Logs page showed "No log lines yet."
even on a live, request-serving instance, and `docker logs` only ever showed the 2 uvicorn
startup lines plus Alembic's own migration-context lines.

**Fix applied:** `database/engine.py::init_db()` now passes
`attributes={"configure_logger": False}` when building the Alembic `Config`; `env.py`
checks `config.attributes.get("configure_logger", True)` and skips `fileConfig()`
entirely for that programmatic path — the app already configures its own root logger
(`legendarr_backend/logging/setup.py::configure_logging()`, called once per
`.claudin/rules/python-conventions.md`), so Alembic never needs to touch it there. Bare
`alembic upgrade`/`db-revision` CLI invocations (no `attributes` set) are unaffected and
still get `fileConfig()`, now with `disable_existing_loggers=False` as an added safety net
for that path. Verified live (rebuilt dev container): `docker logs` and the System → Logs
page both show real INFO-level activity (scheduler job registration, httpx request logs,
etc.) after this fix, not just the 6-line startup stub. Full backend suite (970 tests)
passes unchanged.

**Original finding (kept for context):** the first time `fileConfig()` ran in a test
process (triggered by anything using the `isolated_database` fixture / real `init_db()` /
Alembic migration path), it set `.disabled = True` on every `Logger` object that already
existed and wasn't explicitly declared in `alembic.ini`'s `[loggers]` section — reproduced
with `subtitle_translation.plugins`'s logger: `caplog`-based assertions passed running
`test_plugins.py` alone, but failed with empty `caplog.text` when running the full backend
suite, because an earlier test used `isolated_database` first. Since `fileConfig()` no
longer runs at all on the `init_db()` path, this specific failure mode is now gone too —
a `caplog`-based test on a `legendarr_backend`/`legendarr_web` logger should be safe to
write again, though it wasn't re-verified as part of this fix.
