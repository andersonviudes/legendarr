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
  periodic sync, **and now an HTTP API** (`shared_kernel/api.py::create_api_app()`),
  currently exposing only `/language-profiles/` — the only slice with existing read/write
  functions to wrap. No auth on it yet.
- `modules/web` (package `legendarr_web`) — FastAPI + Jinja2/HTMX UI, no separate JS
  frontend. As of 2026-07-16 it **no longer imports `legendarr_backend` at all** — its
  routers call the backend over real loopback HTTP via `httpx`
  (`shared_kernel/backend_client.py`, base URL from `LEGENDARR_BACKEND_API_URL`, default
  `http://127.0.0.1:8000/api`), not an in-process ASGI shortcut.
- `modules/bootstrap` (package `legendarr_bootstrap`, added 2026-07-16) — the entrypoint
  that brings the other two up together: one FastAPI instance mounting the backend's API app
  at `/api` and the web app at `/`, owning the single `lifespan` that starts/stops the
  scheduler. This is now `make run` / the Docker `CMD`, replacing `legendarr_web` in that
  role — still one process, one port.

Both modules follow **Screaming Architecture + Vertical Slice Architecture**: top-level
folders inside each module are named after business capabilities (`media_providers`,
`subtitle_discovery`, `subtitle_translation`, `language_profiles`, plus web's `dashboard`,
`media_library`), not technical layers. Cross-slice code lives in each module's
`shared_kernel/` (config, database, logging, templates).

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
