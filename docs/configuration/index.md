# Configuration Overview

legendarr is configured entirely through environment variables, all prefixed with
`LEGENDARR_`. They can be set directly or via a `.env` file at the repository root (see
`.env.example`).

```env
LEGENDARR_DATA_DIR=./data
LEGENDARR_RADARR_URL=http://localhost:7878
LEGENDARR_RADARR_API_KEY=
LEGENDARR_SONARR_URL=http://localhost:8989
LEGENDARR_SONARR_API_KEY=
LEGENDARR_SYNC_INTERVAL_MINUTES=15
```

See the [Environment Variables Reference](environment-variables.md) for every setting and
its default.

!!! tip
    Radarr and Sonarr integration is optional and independent — leave a provider's URL
    empty to skip syncing it.
