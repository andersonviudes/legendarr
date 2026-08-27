# External API

*ROADMAP.md 0.17.0 — the same REST API `legendarr_web` already calls internally to drive
the dashboard, documented and exposed for scripts and other tools instead of only ever
being called by the bundled web UI.*

## Base URL

The API is mounted at `/api` on the same process/port as the web UI — e.g.
`http://localhost:8000/api/media/movies`. There's no separate service or port to expose.

## Authentication

Every route requires either an `X-Api-Key` header or a logged-in browser session, unless
login is disabled (Settings → General, see [Authentication](authentication.md)).
For scripts, use the API key shown there:

```bash
curl -H "X-Api-Key: <your-api-key>" http://localhost:8000/api/media/movies
```

`/api/webhooks/*` is the one exception — Radarr/Sonarr's "Connect" calls can't send
custom headers, so it's unauthenticated by design (see
`src/backend/src/legendarr_backend/media_library/webhooks.py`); nothing else should call it.

## Endpoint reference

The full, always-current endpoint list — grouped by domain (Media Library, Language
Profiles, Subtitle Providers, Subtitle Proxies, Translation Providers, Metadata
Providers, Arr Services, Settings, System, Authentication, Webhooks) — is generated
straight from the code, not hand-maintained here:

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- Raw OpenAPI schema: `/api/openapi.json`

All three are reachable without authentication, even when login is enabled — they only
serve the schema/documentation, never data.

## Getting started

The domains most useful for scripting against an existing instance:

- **Media** (`/api/media/*`) — list movies/series, trigger a scan/sync, search/download/
  upload/translate a subtitle for a specific file.
- **Language profiles** (`/api/language-profiles/*`) — CRUD for the profiles that decide
  what gets translated into what.
- **System** (`/api/system/*`) — directory browsing, recent logs, currently running tasks.

Everything else the dashboard's Settings pages configure (Radarr/Sonarr connections,
subtitle/translation/metadata providers, subtitle proxies, task/webhook settings) is
exposed the same way, under its own tag in `/api/docs`.
