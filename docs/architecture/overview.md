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
├── statistics/              # translated/acquired subtitle counts, over time, per profile and provider
├── history/                 # translation/acquisition attempts, successes and failures, merged into one feed
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
├── statistics/              # /statistics/ route
├── system/                  # /system/ route
├── authentication/          # /login, /logout routes (session cookie set/cleared)
├── settings/                # /settings/tasks/, /settings/general/ routes (retry/interval settings, display language + webhook URL + login toggle + API key)
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

### When to extract a subdomain

A slice that piles up loose top-level files is a candidate for grouping some of them into a
subdomain folder, not for splitting into a whole new top-level slice. `subtitle_acquisition/`
is the fullest example: alongside its `providers/` subdomain (the provider adapters), it also
has `blacklist/` (`blacklist_subtitle.py`, `manage_subtitle_blacklist.py`),
`audio_transcription/` (`transcribe_audio.py`, `probe_embedded_audio.py`), and
`candidate_evaluation/` (`match_score.py`, `quality_gate.py`, `release_attributes.py`,
`release_filters.py`). Extract one when:

- **Real coupling, not just a shared topic.** At least 2 files that import each other, or that
  all revolve around the same model/concept — not "these files are kind of related."
- **Name it after the concern, not the slice** (`blacklist/`, not
  `subtitle_blacklist_stuff/`) — the same no-stutter convention `http_client/client.py`
  already follows.
- **`models.py`/`schemas.py`/`router.py`/`jobs.py` stay at the slice's top level, never inside
  a subdomain** — a subdomain holds logic/adapters, not the slice's tables, DTOs, or routes.
- **A helper used by exactly one member of a subdomain moves in with it** (e.g.
  `providers/napiprojekt_hash.py`, used only by `providers/napiprojekt.py`); a helper the
  whole slice depends on stays at the top (e.g. `subtitle_acquisition/opensubtitles_hash.py`,
  used by `search_context.py` to build a search request before any specific provider is
  chosen).
- **Tests don't move.** They stay flat under `tests/<slice>/` with a descriptive name, same as
  `providers/`'s own tests today — only the import path inside each test file changes.
- **It's a trigger to consider, not an obligation.** A slice with 20+ loose top-level files
  and a genuinely cohesive group of 2+ is a candidate; don't force a one-file "subdomain" or
  group files that only share a topic in name — that's speculative structure, not a real fix.
