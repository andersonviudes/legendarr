# Architecture Overview

legendarr is a Python monorepo built with a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
packaged into a single Docker image with one shared `uv.lock`.

## Modules

- **`modules/backend`** (`legendarr_backend`) — domain logic: Radarr/Sonarr clients,
  subtitle discovery, subtitle translation, language profiles, the scheduler that runs the
  media sync periodically, and an HTTP API (`shared_kernel/api.py`) exposing that domain
  logic — currently `/language-profiles/*`.
- **`modules/web`** (`legendarr_web`) — the web UI (FastAPI + Jinja2/HTMX): templates,
  static/JS, and per-slice "services" that call `legendarr_backend`'s API over HTTP
  (`httpx`). It has no Python dependency on `legendarr_backend` and never imports its code.
- **`modules/bootstrap`** (`legendarr_bootstrap`) — the entrypoint that brings the other two
  modules up together: it mounts `legendarr_backend`'s API app at `/api` and
  `legendarr_web`'s app at `/` behind one FastAPI instance, and owns the single `lifespan`
  that starts/stops the backend's scheduler. This is `make run` / the Docker `CMD` — a
  single process still serves the dashboard, the API, and the background sync job.

## Screaming Architecture + Vertical Slice Architecture

Inside each module, code is organized by **business capability**, not technical layer.
Top-level folders are named after what the code *does*, not what kind of code it is:

```text
modules/backend/src/legendarr_backend/
├── media_providers/        # Radarr/Sonarr clients, media library sync
├── subtitle_discovery/      # finding subtitle tracks (external + embedded)
├── subtitle_translation/    # translation providers and the translate step
├── language_profiles/       # language profile model + management
└── shared_kernel/           # config, database, logging — genuinely cross-slice code

modules/web/src/legendarr_web/
├── dashboard/               # home page — profile-count stats, polls via htmx
├── media_library/           # /media/movies, /media/series routes
├── language_profiles/       # /settings/ route
├── history/                 # /history/ route
├── system/                  # /system/ route
└── shared_kernel/            # templates, cross-slice web concerns
```

Each slice contains what it needs to work end to end. Code that's truly shared across
slices — configuration, database setup, logging, templates — lives in `shared_kernel/`.

When adding a new feature, create a new top-level slice folder named after the business
capability, in whichever module owns it, rather than adding to an existing generic layer.
