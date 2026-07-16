---
name: legendarr project architecture
description: Repo layout, tech stack, and conventions for the legendarr project (subtitle translation for Radarr/Sonarr)
type: project
---

legendarr is a self-hosted subtitle-translation companion for Radarr and Sonarr, with rich
language-profile configuration and support for translating embedded subtitle tracks, not
just external files. Bootstrapped 2026-07-15. All repo content (README, UI copy, comments)
is English-only — the user asked to drop an earlier Portuguese README/UI and any comparison
to other subtitle tools by name.

**Structure:** Python monorepo, uv workspace with three members under `modules/` (as of
2026-07-16, PR #2 "feat/bootstrap-module"):
- `modules/backend` (package `legendarr_backend`) — domain logic: Radarr/Sonarr clients,
  subtitle discovery/translation, language profiles (SQLModel + SQLite), APScheduler-based
  periodic sync, **and now an HTTP API** (`api.py::create_api_app()`),
  currently exposing only `/language-profiles/` — the only slice with existing read/write
  functions to wrap. No auth on it yet.
- `modules/web` (package `legendarr_web`) — FastAPI + Jinja2/HTMX UI, no separate JS
  frontend. As of 2026-07-16 it **no longer imports `legendarr_backend` at all** — its
  routers call the backend over real loopback HTTP via `httpx`
  (`backend_client/client.py`, base URL from `LEGENDARR_BACKEND_API_URL`, default
  `http://127.0.0.1:8000/api`), not an in-process ASGI shortcut.
- `modules/bootstrap` (package `legendarr_bootstrap`, added 2026-07-16) — the entrypoint
  that brings the other two up together: one FastAPI instance mounting the backend's API app
  at `/api` and the web app at `/`, owning the single `lifespan` that starts/stops the
  scheduler. This is now `make run` / the Docker `CMD`, replacing `legendarr_web` in that
  role — still one process, one port.

Both modules follow **Screaming Architecture + Vertical Slice Architecture**: top-level
folders inside each module are named after business capabilities (`media_library`,
`subtitle_discovery`, `subtitle_translation`, `language_profiles`, plus web's `dashboard`,
`media_library`), not technical layers. A domain folder can hold its own **subdomains** —
`media_library/providers/` (Radarr/Sonarr technical adapters) and
`subtitle_translation/providers/` (translation-provider adapters) separate a domain's
business logic from the raw external-API clients it calls.

**2026-07-16, reorg #2 (domain-driven slices, PR `refactor/domain-driven-slices`):**
`shared_kernel/` was eliminated as a wrapper folder in both modules — each of its subject
subfolders was promoted to the module's top level, as a sibling of the business-domain
folders, instead of nested under one "shared" umbrella: backend now has top-level `config/`
(`settings.py` env vars + `config_file.py` on-disk `config.yaml`), `database/` (`engine.py`),
`http_client/` (`client.py`), `logging/` (`setup.py`), and `api.py` (was
`shared_kernel/api/app.py`, now a single top-level module file mirroring
`legendarr_web/app.py`'s shape — it imports every domain's router directly, so it's no
longer "shared code reaching into a domain slice"); web has top-level `config/`
(`settings.py`), `backend_client/` (`client.py`), `templates/` (`loader.py` + `base.html`).
Also renamed backend's `media_providers/` → `media_library/` to match web's naming for the
same business capability, splitting it into `media_library/sync_media_library.py` (business
logic) + `media_library/providers/{base,radarr_client,sonarr_client}.py` (technical
adapters, mirroring `subtitle_translation/providers/`). Two file-relative path constants
had to be corrected for the removed nesting level: `database/engine.py`'s
`Path(__file__).resolve().parents[4]` (alembic.ini lookup) → `parents[3]`, and
`templates/loader.py`'s `TEMPLATES_ROOT = Path(__file__).resolve().parent.parent.parent`
→ `.parent.parent`. `dashboard/router.py`'s import of `language_profiles/service.py` was
deliberately left unchanged (only its import path updated) — reuse of another slice's
public entry point, not an inversion to fix, per the Clean Code "don't duplicate logic
across slices" rule.

Every file inside a top-level shared folder is named for its *concern* (`client.py`,
`settings.py`, `engine.py`), never repeating the folder's own name (`http_client/http_client.py`
would be a stutter) — same convention domain slices already use (e.g.
`language_profiles/manage_language_profile.py`, not `language_profiles/router.py` named
after the folder). `logging/setup.py` (not `logging.py`) also sidesteps shadowing the
stdlib `logging` module it imports internally.

**2026-07-16, post-reorg cleanup (same PR):** a 3-agent audit of the reorg above (stale-path
sweep, architecture-compliance check, orphaned-files check) found no leftover `shared_kernel`/
`media_providers` references anywhere, but surfaced three PRE-EXISTING gaps (not caused by the
reorg — confirmed identical on `main` before it) that were fixed in the same PR while at it:
1. `modules/web/tests/` was flat (`test_dashboard.py` etc. directly under `tests/`), not
   mirroring `legendarr_web`'s slice folders per AGENTS.md's "`tests/<slice>/test_*.py`" rule
   — moved into `tests/dashboard/`, `tests/history/`, `tests/language_profiles/`,
   `tests/media_library/` (holds both `test_movies_page.py` and `test_series_page.py`, since
   both routes live in the one `media_library/router.py`), `tests/system/`. `conftest.py`
   stays at `tests/` root (session-scoped autouse fixture, applies to the whole module, same
   placement as `modules/bootstrap/tests/conftest.py`).
2. `test_dashboard.py`/`test_settings_page.py` imported `legendarr_backend.api` directly to
   spin up an in-process ASGI backend (`httpx.ASGITransport`) for the `get_backend_client`
   override — a real violation of "`legendarr_web` never imports `legendarr_backend`" (this
   predates the reorg; the reorg only updated the import's path, from
   `legendarr_backend.shared_kernel.api.app`). Fixed by swapping `ASGITransport` for
   `httpx.MockTransport` returning a canned `[]` JSON response for `GET /language-profiles/`,
   same pattern already used in `modules/backend/tests/http_client/test_http_client.py`. Web
   tests now have zero imports of `legendarr_backend`.
3. `logging/setup.py` had no test at all (true both before and after the reorg) — added
   `modules/backend/tests/logging/test_setup.py`, monkeypatching `logging.basicConfig` to
   assert `configure_logging()`'s `level`/`stream` kwargs.

**Tooling:** `uv` (workspace root `pyproject.toml` is virtual, `tool.uv.package = false`),
`ruff` for lint+format, `pytest`, SQLite for persistence. Single `Dockerfile` builds both
modules into one image (must pass `--all-packages` to `uv sync` in the Dockerfile — omitting
it only syncs the virtual root and silently produces an empty venv, a bug hit during bootstrap).
CI (`.github/workflows/ci.yml`) lints/tests on every push+PR to main, then only validates
that the Docker image builds (`push: false`) — it does not publish to a registry. (CI
originally published to `ghcr.io/andersonviudes/legendarr` on push to main; the user asked
2026-07-15 to drop the publish step and keep CI to build+test only.)

**Why:** these choices came from an explicit AskUserQuestion round with the user: Python-only
web UI (no React/TS), uv over Poetry, SQLite over Postgres. The initial "build+publish"
CI scope was later narrowed to "build+test only" per user request. The 2026-07-16
backend/web split was also an explicit AskUserQuestion round: single-process/single-port
topology was chosen over two-process (backend on its own internal port) or two-container
splits, consistent with the self-hosted single-user framing behind the earlier SQLite choice;
no auth was added to the new backend API since ROADMAP.md 0.15.0/0.16.0 (auth & external API)
haven't landed — it's treated as internal-only for now. Note this intentionally overlaps with
ROADMAP.md's 0.16.0 "External API" item but is much narrower (unauthenticated,
language-profiles only) — don't treat 0.16.0 as done because of it.

**How to apply:** when adding a new feature, create a new top-level slice folder named after
the business capability inside the right module (backend for domain logic, web for UI/routes)
rather than adding to an existing generic layer. Keep the Dockerfile's `uv sync` calls using
`--all-packages`.

**AGENTS.md kept lean (2026-07-16):** `AGENTS.md`'s Architecture section only summarizes the
three modules and points to this doc's `docs/architecture/overview.md` for the full slice
layout — don't re-inline the detailed folder tree there, it drifted out of sync with the
module split once before (still said "two modules" after `bootstrap` was added). Ruff/env-var
conventions live in `.claudin/rules/python-conventions.md` (path-scoped to `modules/**/*.py`)
instead of inline in `AGENTS.md`, and the Alembic migration workflow (incl. the `env.py`
caching gotcha above) is now the `db-migration` skill — update those files, not `AGENTS.md`,
when this detail changes.
