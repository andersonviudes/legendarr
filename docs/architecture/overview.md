# Architecture Overview

legendarr is a Python monorepo built with a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
packaged into a single Docker image with one shared `uv.lock`.

## Modules

- **`src/backend`** (`legendarr_backend`) — domain logic: Radarr/Sonarr connection
  management, media library sync, subtitle discovery, subtitle translation, language
  profiles, the scheduler that runs the media sync periodically, and an HTTP API (`api.py`)
  exposing that domain logic — currently `/language-profiles/*` and `/arr-services/*`.
- **`src/web`** (`legendarr_web`) — the web UI (FastAPI + Jinja2/HTMX): templates,
  static/JS, and per-slice "services" that call `legendarr_backend`'s API over HTTP
  (`httpx`). It has no Python dependency on `legendarr_backend` and never imports its code.
- **`src/bootstrap`** (`legendarr_bootstrap`) — the entrypoint that brings the other two
  modules up together: it mounts `legendarr_backend`'s API app at `/api` and
  `legendarr_web`'s app at `/` behind one FastAPI instance, and owns the single `lifespan`
  that starts/stops the backend's scheduler. This is `make run` / the Docker `CMD` — a
  single process still serves the dashboard, the API, and the background sync job.

## Screaming Architecture + Vertical Slice Architecture

Inside each module, code is organized by **business capability**, not technical layer.
Top-level folders are named after what the code *does*, not what kind of code it is:

```text
src/backend/src/legendarr_backend/
├── arr_services/            # Radarr/Sonarr connection CRUD + connection testing
├── language_profiles/       # language profile model + management
├── media_library/           # media library sync (business logic)
│   └── jobs.py               # the APScheduler job that drives the sync
├── subtitle_acquisition/    # subtitle-provider registration (credentials, test connection)
│   └── providers/            # subdomain: SubtitleProvider protocol (interface only)
├── media_metadata/          # TheTVDB/IMDb/TMDb metadata provider registration + fetch-on-sync/refetch
│   └── providers/            # subdomain: MetadataProvider protocol + TVDB/OMDb/TMDb clients
├── subtitle_discovery/      # finding subtitle tracks (external + embedded)
├── subtitle_translation/    # translation providers and the translate step
│   └── providers/            # subdomain: translation-provider adapters
├── subtitle_timing_sync/    # manual, per-subtitle ffsubsync timing-correction pass
├── authentication/          # session-based login (AuthSession) + API key issuance (ROADMAP 0.16.0)
├── settings/                # task/translation-default/webhook runtime settings
├── system/                  # directory browsing, recent logs, running-task status
├── arr_clients/             # shared Radarr/Sonarr API clients (sync + connection test)
├── config/                  # env Settings + on-disk config.yaml
├── database/                # SQLModel engine/session + Alembic migration trigger
├── http_client/             # shared outbound-HTTP conventions for provider clients
├── logging/                 # logging setup
├── scheduling/              # shared APScheduler wrapper (scheduler, queues, retry)
├── security/                # secrets encryption at rest (Fernet key, encrypt/decrypt, EncryptedString column type)
└── api.py                   # the internal HTTP API app

src/web/src/legendarr_web/
├── dashboard/               # home page — profile-count stats, polls via htmx
├── arr_services/            # /settings/arr-services/ routes (CRUD, test, enable/disable)
├── subtitle_acquisition/    # /settings/subtitle-providers/ routes (enable, credentials, test)
├── media_metadata/          # /settings/metadata-source/ routes (enable, credentials, test, refetch)
├── language_profiles/       # /settings/ route
├── subtitle_translation/    # /settings/translation-providers/ routes (enable, credentials, test, default)
├── media_library/           # /media/movies, /media/series routes
├── history/                 # /history/ route
├── system/                  # /system/ route
├── authentication/          # /login, /logout routes (session cookie set/cleared)
├── settings/                # /settings/tasks/, /settings/authentication/ routes (retry/interval settings, login toggle + API key)
├── subtitle_proxies/        # /settings/subtitle-proxies/ routes (CRUD, test, enable/disable)
├── config/                  # env WebSettings
├── backend_client/          # httpx client for calling the backend API
└── templates/               # shared Jinja2Templates factory + base.html layout
```

Each slice contains what it needs to work end to end. A domain folder can hold its own
**subdomains** — e.g. `subtitle_translation/providers/` separates a domain's business logic
from the raw external-API adapters it calls. Code that's truly shared across slices —
configuration, database setup, logging, templates, the APScheduler wrapper, secrets
encryption at rest, and the Radarr/Sonarr API clients (used by both `media_library` sync
and `arr_services` connection testing) — lives in its own top-level folder (`arr_clients/`,
`config/`, `database/`, `http_client/`, `logging/`, `scheduling/`, `security/`; web's
`config/`, `backend_client/`, `templates/`),
a sibling of the business-domain folders rather than nested under one shared-code wrapper.

When adding a new feature, create a new top-level slice folder named after the business
capability, in whichever module owns it, rather than adding to an existing generic layer.
