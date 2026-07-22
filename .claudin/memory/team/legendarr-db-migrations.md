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
- `modules/backend/src/legendarr_backend/config/config_file.py` (promoted out of
  `shared_kernel/` to the module's top level 2026-07-16, see `legendarr-architecture.md`) —
  `AppConfigFile`/`load_or_create_config_file()`. On first run, writes
  `{LEGENDARR_DATA_DIR}/config.yaml` (e.g. `/config/config.yaml` in Docker) with
  `database_url` defaulted from `Settings.resolved_database_url`. From then on, `config.yaml`
  — not `LEGENDARR_DATABASE_URL` — is the source of truth `database.py.get_engine()` reads.
  This is the file the future Settings feature (0.4.0) will read/rewrite.
- `database.py.init_db()` now runs `alembic.command.upgrade(cfg, "head")` instead of
  `SQLModel.metadata.create_all()`, automatically at every app startup (self-hosted operators
  shouldn't need a manual migration step) — `bootstrap.py`'s single `init_db()` call site is
  unchanged.

  **Update 2026-07-22:** `modules/bootstrap/src/legendarr_bootstrap/app.py`'s own `lifespan()`
  now *also* calls `init_db()`, before anything that touches the database in that lifespan
  (currently `ensure_subtitle_providers_seeded()`). Reason: `app.py` mounts `api_app` — whose
  own lifespan is what originally called `init_db()` — via `app.mount("/api", api_app)` on an
  outer `FastAPI(lifespan=lifespan)` with its *own* custom lifespan function; mounting doesn't
  chain the mounted app's lifespan into the outer one, so nothing guarantees the schema exists
  before the outer lifespan's own startup code runs. `init_db()` is idempotent (a no-op
  "upgrade head" if already current), so calling it from both places is safe by design, not
  an oversight — any future startup code added to `bootstrap/app.py`'s `lifespan()` that reads
  the database needs `init_db()` to have already run there, not just in `api_app`.
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

**Also note:** `AGENTS.md` didn't exist on `main` (only on the still-unmerged
`feat/web-ui-shell` branch, added there in commit `49417a1`) — brought it onto `main` via this
branch instead of waiting for that branch to merge (materialized from `feat/web-ui-shell:AGENTS.md`,
updated with the `db-revision`/`db-upgrade` targets and the release-only Docker build note). If
`feat/web-ui-shell` merges later, watch for a duplicate/conflicting `AGENTS.md` add.

**Why:** avoids re-debugging the same `env.py` caching gotcha, and explains why `config.yaml`
takes precedence over the env var on anything but the very first run.

**How to apply:** when adding new SQLModel tables, import their model module in
`db/migrations/env.py` (next to the existing `language_profiles.models` import) so
`--autogenerate` picks them up, then run `make db-revision message="..."`.

**2026-07-22 — autogenerate never handles a new FK column correctly on SQLite:** confirmed a
third time (after `35527f37e677` and `3605a01d1781`) while adding `SubtitleProxy` +
`SubtitleProviderConfig.proxy_id`. `alembic revision --autogenerate` emits a plain
`op.add_column(...)` + `op.create_foreign_key(...)` for a new FK column on an *existing* table,
which fails at `db-upgrade` time with `NotImplementedError: No support for ALTER of constraints
in SQLite dialect` — SQLite can't `ALTER` a constraint directly. Always hand-rewrite that part
of the generated migration to wrap the add_column/create_index/create_foreign_key in
`op.batch_alter_table("<table>")`, with an explicit FK constraint name (existing convention:
`fk_<table>_<column>_<referenced_table>`) since batch mode needs one to target it in a later
`drop_constraint`. New tables created from scratch (`op.create_table(...)`) don't need this —
only a new FK column on a table that already exists. Also: since SQLite DDL isn't
transactional, a migration that fails partway through (as this one did before the fix) can
leave the dev DB in a partial state — `alembic_version` stuck at the old revision while the
new table/column already exist. The dev `data/` directory is gitignored, so the fastest fix is
deleting it entirely (`rm -rf data modules/backend/data`) and re-running `make db-upgrade` from
a clean slate, rather than trying to hand-reconcile the partial schema.
