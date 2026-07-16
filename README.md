# legendarr

Self-hosted companion for **Radarr** and **Sonarr** that automatically translates
subtitles, with flexible language profiles and the ability to translate any subtitle,
including tracks embedded inside the video.

Full documentation: **https://andersonviudes.github.io/legendarr** — see [ROADMAP.md](ROADMAP.md)
for what's planned.

## Architecture

The project is a Python monorepo with two modules, packaged into a single build (one
Docker image, one `uv.lock`):

- **`modules/backend`** (`legendarr_backend`) — domain: Radarr/Sonarr integration,
  subtitle discovery and extraction, translation, language profiles, and the scheduler
  that runs all of it periodically.
- **`modules/web`** (`legendarr_web`) — web UI (FastAPI + Jinja2/HTMX), consumes the
  backend services directly and starts the backend's scheduler in its own process.

Inside each module, the code is organized using **Screaming Architecture + Vertical
Slice Architecture**: top-level folders are named after business capabilities
(`media_library`, `subtitle_discovery`, `subtitle_translation`, `language_profiles`, ...),
not technical layers. Each slice contains what it needs to work end to end; genuinely
shared code lives in its own top-level folder (`config/`, `database/`, `logging/`,
`templates/`, ...), a sibling of the business-domain folders.

## Running locally

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
make install   # uv sync --all-packages
make run       # starts the web app (and the backend scheduler) at http://localhost:8000
```

Configuration is done via environment variables (see `.env.example`), prefix `LEGENDARR_`:
Radarr/Sonarr URLs and API keys, sync interval, data directory, etc.

## Tests and lint

```bash
make test
make lint
```

## Docker

A single `Dockerfile` builds both modules and runs the web app (which starts the
backend's scheduler internally):

```bash
make docker-build
docker run -p 8000:8000 -v ./data:/config legendarr:local
```

## CI

The workflow in `.github/workflows/ci.yml` runs lint + tests, then validates that the
Docker image builds, on every PR and push to `main`. It does not publish the image.

## Documentation

The docs site lives in `docs/` (MkDocs + Material) and is deployed to GitHub Pages by
`.github/workflows/docs.yml` on every push to `main` that touches `docs/` or `mkdocs.yml`.
Preview it locally with:

```bash
make docs-install
make docs-serve
```
