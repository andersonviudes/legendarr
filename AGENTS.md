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
make bump-version part=patch  # bump version across the workspace (patch|minor|major)
make docker-build  # docker build -t legendarr:local .
make docs-serve    # preview the MkDocs site locally (needs `make docs-install` first)
```

Always run `make lint` and `make test` before considering a change done — CI (`.github/workflows/ci.yml`)
enforces both on every push/PR to `main`. The Docker image is only built (to validate it, not
pushed anywhere) when a GitHub Release is published, not on every push/PR — publishing it to a
registry is a `1.0.0` roadmap milestone, not wired up yet (see `ROADMAP.md`).

## Versioning & releases

One version, shared by the root `pyproject.toml` and every workspace member (`src/backend`,
`src/web`, `src/bootstrap`) — they must always match, since they ship as one Docker image, not
separate published packages. It follows `ROADMAP.md`'s `0.x.0` milestones (bumped when a
milestone's items are fully checked off), climbing to `1.0.0` once every roadmap use case works
together and the image is published.

- Bump locally with `make bump-version part=patch|minor|major` (wraps
  `scripts/bump_version.sh`, which re-locks `uv.lock` too).
- Or trigger the `Release` workflow (`.github/workflows/release.yml`) from the Actions tab,
  which bumps the version, commits and pushes straight to `main` (mechanical `chore:` commit,
  same exception as `fix:`/`docs:` — see `.claudin/memory/team/legendarr-branch-convention.md`),
  tags it `vX.Y.Z`, and creates the GitHub Release. That publish event is what `ci.yml`'s
  `docker-build` job listens for.
- The workflow needs repo Settings → Actions → General → Workflow permissions set to "Read and
  write permissions" for the default `GITHUB_TOKEN` to be able to push/tag/release.

## Architecture

Python monorepo, one `uv` workspace (`pyproject.toml` → `[tool.uv.workspace] members = ["src/*"]`),
built into a single Docker image with one shared `uv.lock`. Three modules — full breakdown
and slice layout in `docs/architecture/overview.md`:

- `src/backend` (`legendarr_backend`) — domain logic (Radarr/Sonarr clients, subtitle
  discovery/translation, language profiles, sync scheduler) plus an internal HTTP API.
- `src/web` (`legendarr_web`) — FastAPI + Jinja2/HTMX UI; calls the backend's API over
  loopback HTTP, never imports `legendarr_backend` directly.
- `src/bootstrap` (`legendarr_bootstrap`) — entrypoint (`make run` / Docker `CMD`) that
  mounts both apps behind one FastAPI instance and owns the scheduler's `lifespan`.

`backend` and `web` both use **Screaming Architecture + Vertical Slice Architecture**:
top-level folders are business capabilities, not technical layers — new features get a new
slice folder in whichever module owns them, not a new generic layer. Tests mirror this:
`src/<module>/tests/<slice>/test_*.py`.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`, `test:`, ...).
- New features go on a feature branch with a PR into `main` — don't push those directly to
  `main`. Bug fixes (`fix:` commits) can be committed and pushed straight to `main`.
- Python style, Ruff config, and env var conventions: see `.claudin/rules/python-conventions.md`
  (loads automatically when touching `src/**/*.py`).
- Clean Code / SOLID guidance: see `.claudin/rules/clean-code-solid.md` (same trigger).

Subdirectory `AGENTS.md` files can be added under `src/backend/`, `src/web/`, or
`src/bootstrap/` for module-specific instructions if any of them grows enough to need them.

To refine: `/create` (skills, rules, agents), `/agents` (subagents), `/skills` (skills), `/permissions` (viewer for permission rules — edit `settings.json` directly to change them).
