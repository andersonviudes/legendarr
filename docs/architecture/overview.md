# Architecture Overview

legendarr is a Python monorepo built with a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
packaged into a single Docker image with one shared `uv.lock`.

## Modules

- **`modules/backend`** (`legendarr_backend`) — domain logic: Radarr/Sonarr clients,
  subtitle discovery, subtitle translation, language profiles, and the scheduler that runs
  the media sync periodically.
- **`modules/web`** (`legendarr_web`) — the web UI (FastAPI + Jinja2/HTMX). It depends on
  `legendarr_backend` directly and starts the backend's scheduler in its own FastAPI
  `lifespan`, so a single process serves both the dashboard and the background sync job.

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
├── dashboard/               # home page
├── media_library/           # /media/ route
├── language_profiles/       # /language-profiles/ route
└── shared_kernel/            # templates, cross-slice web concerns
```

Each slice contains what it needs to work end to end. Code that's truly shared across
slices — configuration, database setup, logging, templates — lives in `shared_kernel/`.

When adding a new feature, create a new top-level slice folder named after the business
capability, in whichever module owns it, rather than adding to an existing generic layer.
