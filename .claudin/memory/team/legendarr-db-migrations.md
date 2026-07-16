---
name: legendarr Alembic migrations and config.yaml
description: How database migrations and DB-location config work in legendarr backend (ROADMAP.md 0.1.0 item), added 2026-07-15
type: project
---

Implemented the ROADMAP.md 0.1.0 "Database infrastructure" item on branch `feat/db-migrations`
(branched from `main`, not from `feat/web-ui-shell`). Kept SQLite (explicit decision, see
`legendarr-architecture.md`) — this only adds migration tooling around it, no engine swap.

**Layout:**
- `modules/backend/alembic.ini` + `modules/backend/db/migrations/{env.py,script.py.mako,versions/}`
  — module-scoped (backend owns the DB), not a top-level `db/` at the repo root.
- `modules/backend/src/legendarr_backend/shared_kernel/config_file.py` — new
  `AppConfigFile`/`load_or_create_config_file()`. On first run, writes
  `{LEGENDARR_DATA_DIR}/config.yaml` (e.g. `/config/config.yaml` in Docker) with
  `database_url` defaulted from `Settings.resolved_database_url`. From then on, `config.yaml`
  — not `LEGENDARR_DATABASE_URL` — is the source of truth `database.py.get_engine()` reads.
  This is the file the future Settings feature (0.4.0) will read/rewrite.
- `database.py.init_db()` now runs `alembic.command.upgrade(cfg, "head")` instead of
  `SQLModel.metadata.create_all()`, automatically at every app startup (self-hosted operators
  shouldn't need a manual migration step) — `bootstrap.py`'s single `init_db()` call site is
  unchanged.
- `make db-revision message="..."` / `make db-upgrade` — manual escape hatches, still run
  migrations through the same `alembic.ini`.

**Non-obvious gotcha fixed during implementation:** `db/migrations/env.py` must NOT
unconditionally resolve `sqlalchemy.url` from `get_settings()`/`config_file` — `get_settings()`
is `@lru_cache`d process-wide, so doing that unconditionally makes `env.py` ignore whatever URL
`database.py.init_db()` already set on the `Config` object (breaks tests that monkeypatch
settings, and in one case leaked a real `./data/legendarr.db` + `config.yaml` into the repo
root during a test run). Fix: `env.py` only resolves its own URL `if not
config.get_main_option("sqlalchemy.url")` — i.e. only for standalone `alembic`/`make
db-upgrade` CLI invocations, never when a caller already set it programmatically. `alembic.ini`'s
`sqlalchemy.url` is left blank (not the `driver://...` placeholder) so that falsy-check works.

**Also note:** `AGENTS.md` doesn't exist on `main` (only on the still-unmerged
`feat/web-ui-shell` branch, added there in commit `49417a1`) — so the "update AGENTS.md
commands section" step from this task's plan was skipped; redo it once that branch merges.

**Why:** avoids re-debugging the same `env.py` caching gotcha, and explains why `config.yaml`
takes precedence over the env var on anything but the very first run.

**How to apply:** when adding new SQLModel tables, import their model module in
`db/migrations/env.py` (next to the existing `language_profiles.models` import) so
`--autogenerate` picks them up, then run `make db-revision message="..."`.
