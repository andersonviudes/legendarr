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
make run           # runs legendarr-bootstrap (web UI + backend API + scheduler) at http://localhost:8000
make db-revision message="..."  # generate an Alembic migration (use the `db-migration` skill)
make db-upgrade    # apply pending Alembic migrations
make docker-build  # docker build -t legendarr:local .
make docs-serve    # preview the MkDocs site locally (needs `make docs-install` first)
```

Always run `make lint` and `make test` before considering a change done — CI (`.github/workflows/ci.yml`)
enforces both on every push/PR to `main`. The Docker image is only built when a GitHub Release is
published, not on every push/PR.

## Architecture

Python monorepo, one `uv` workspace (`pyproject.toml` → `[tool.uv.workspace] members = ["modules/*"]`),
built into a single Docker image with one shared `uv.lock`. Three modules — full breakdown
and slice layout in `docs/architecture/overview.md`:

- `modules/backend` (`legendarr_backend`) — domain logic (Radarr/Sonarr clients, subtitle
  discovery/translation, language profiles, sync scheduler) plus an internal HTTP API.
- `modules/web` (`legendarr_web`) — FastAPI + Jinja2/HTMX UI; calls the backend's API over
  loopback HTTP, never imports `legendarr_backend` directly.
- `modules/bootstrap` (`legendarr_bootstrap`) — entrypoint (`make run` / Docker `CMD`) that
  mounts both apps behind one FastAPI instance and owns the scheduler's `lifespan`.

`backend` and `web` both use **Screaming Architecture + Vertical Slice Architecture**:
top-level folders are business capabilities, not technical layers — new features get a new
slice folder in whichever module owns them, not a new generic layer. Tests mirror this:
`modules/<module>/tests/<slice>/test_*.py`.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`, `test:`, ...).
- Work happens on feature branches with a PR into `main` — don't push directly to `main`.
- Python style, Ruff config, and env var conventions: see `.claudin/rules/python-conventions.md`
  (loads automatically when touching `modules/**/*.py`).
- Clean Code / SOLID guidance: see `.claudin/rules/clean-code-solid.md` (same trigger).

Subdirectory `AGENTS.md` files can be added under `modules/backend/`, `modules/web/`, or
`modules/bootstrap/` for module-specific instructions if any of them grows enough to need them.

To refine: `/create` (skills, rules, agents), `/agents` (subagents), `/skills` (skills), `/permissions` (viewer for permission rules — edit `settings.json` directly to change them).
