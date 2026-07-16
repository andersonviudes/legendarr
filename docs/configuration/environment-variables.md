# Environment Variables Reference

All variables are prefixed with `LEGENDARR_` and read via `legendarr_backend.shared_kernel.config.settings.Settings`
(or `legendarr_web.shared_kernel.config.settings.WebSettings` for the `LEGENDARR_BACKEND_API_URL` variable).

| Variable | Default | Description |
| --- | --- | --- |
| `LEGENDARR_DATA_DIR` | `./data` | Directory for the SQLite database and other persisted data. Mounted as `/config` in the Docker image. |
| `LEGENDARR_DATABASE_URL` | *(derived from `DATA_DIR`)* | Override the SQLAlchemy database URL used the first time `config.yaml` is created, instead of the default SQLite file. Ignored on later runs — see the note below. |
| `LEGENDARR_RADARR_URL` | *(empty)* | Base URL of your Radarr instance. Leave empty to skip Radarr sync. |
| `LEGENDARR_RADARR_API_KEY` | *(empty)* | Radarr API key. |
| `LEGENDARR_SONARR_URL` | *(empty)* | Base URL of your Sonarr instance. Leave empty to skip Sonarr sync. |
| `LEGENDARR_SONARR_API_KEY` | *(empty)* | Sonarr API key. |
| `LEGENDARR_SYNC_INTERVAL_MINUTES` | `15` | How often the background scheduler resyncs the media library. |
| `LEGENDARR_BACKEND_API_URL` | `http://127.0.0.1:8000/api` | Base URL `legendarr_web` uses to call `legendarr_backend`'s API. Only relevant when running `legendarr_web` standalone against a separately-hosted backend — the default is correct for the normal `legendarr_bootstrap` single-process deploy. |

!!! note
    If `LEGENDARR_DATABASE_URL` is unset, legendarr resolves it to
    `sqlite:///{LEGENDARR_DATA_DIR}/legendarr.db` and creates `LEGENDARR_DATA_DIR` if it
    doesn't exist.

!!! note
    On first run, legendarr writes that resolved database location to
    `{LEGENDARR_DATA_DIR}/config.yaml`. From then on, `config.yaml` — not
    `LEGENDARR_DATABASE_URL` — is the source of truth for where the database lives; it's the
    file the Settings feature will read and rewrite. Database schema changes are applied via
    Alembic migrations (`modules/backend/db/migrations/`), run automatically at startup.
