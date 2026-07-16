# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

legendarr is a self-hosted companion for Radarr and Sonarr that translates subtitles
(including embedded tracks). Full docs: `docs/` (see `docs/architecture/overview.md`
for the deeper architecture writeup), deployed to https://andersonviudes.github.io/legendarr.

## Commands

```bash
make install       # uv sync --all-packages
make lint          # ruff check . && ruff format --check .
make format        # ruff format .
make test          # uv run pytest
make run           # runs the web app (+ backend scheduler) at http://localhost:8000
make db-revision message="..."  # generate an Alembic migration from model changes
make db-upgrade    # apply pending Alembic migrations
make docker-build  # docker build -t legendarr:local .
make docs-serve    # preview the MkDocs site locally (needs `make docs-install` first)
```

Always run `make lint` and `make test` before considering a change done — CI (`.github/workflows/ci.yml`)
enforces both on every push/PR to `main`. The Docker image is only built when a GitHub Release is
published, not on every push/PR.

## Architecture

Python monorepo, one `uv` workspace (`pyproject.toml` → `[tool.uv.workspace] members = ["modules/*"]`),
built into a single Docker image with one shared `uv.lock`.

- `modules/backend` (`legendarr_backend`) — domain logic: Radarr/Sonarr clients, subtitle
  discovery/translation, language profiles, the sync scheduler.
- `modules/web` (`legendarr_web`) — FastAPI + Jinja2/HTMX UI. Depends on `legendarr_backend`
  directly and starts its scheduler in the FastAPI `lifespan`.

Both modules use **Screaming Architecture + Vertical Slice Architecture**: top-level folders
are named after business capabilities (`media_providers`, `subtitle_discovery`,
`subtitle_translation`, `language_profiles`, ...), not technical layers. When adding a
feature, create a new top-level slice folder in whichever module owns it — don't add to an
existing generic layer. Code genuinely shared across slices (config, database, logging,
templates) goes in `shared_kernel/`, nowhere else.

Tests mirror this layout: `modules/<module>/tests/<slice>/test_*.py`.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`, `test:`, ...).
- Work happens on feature branches with a PR into `main` — don't push directly to `main`.
- Config is env vars prefixed `LEGENDARR_`, loaded via `pydantic-settings` (see `.env.example`
  and `docs/configuration/environment-variables.md`). Don't hardcode Radarr/Sonarr URLs or
  keys.
- Ruff config (`pyproject.toml`): line length 100, `target-version py312`, and an explicit
  lint `select` list (`E, F, I, UP, B`) — narrower than Ruff's default rule set.

Subdirectory `AGENTS.md` files can be added under `modules/backend/` or `modules/web/` for
module-specific instructions if either grows enough to need them.

To refine: `/create` (skills, rules, agents), `/agents` (subagents), `/skills` (skills), `/permissions` (viewer for permission rules — edit `settings.json` directly to change them).
