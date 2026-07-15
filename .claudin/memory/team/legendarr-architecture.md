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

**Structure:** Python monorepo, uv workspace with two members under `modules/`:
- `modules/backend` (package `legendarr_backend`) — domain logic: Radarr/Sonarr clients,
  subtitle discovery/translation, language profiles (SQLModel + SQLite), APScheduler-based
  periodic sync.
- `modules/web` (package `legendarr_web`) — FastAPI + Jinja2/HTMX UI, no separate JS frontend.
  It depends on `legendarr_backend` directly (single process) and starts the backend's
  scheduler in its own FastAPI `lifespan`.

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
CI scope was later narrowed to "build+test only" per user request.

**How to apply:** when adding a new feature, create a new top-level slice folder named after
the business capability inside the right module (backend for domain logic, web for UI/routes)
rather than adding to an existing generic layer. Keep the Dockerfile's `uv sync` calls using
`--all-packages`.
