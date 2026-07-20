# Environment Variables Reference

All variables are prefixed with `LEGENDARR_` and read via `legendarr_backend.config.settings.Settings`
(or `legendarr_web.config.settings.WebSettings` for the `LEGENDARR_BACKEND_API_URL` variable).

| Variable | Default | Description |
| --- | --- | --- |
| `LEGENDARR_DATA_DIR` | `./data` | Directory for the SQLite database and other persisted data. Mounted as `/config` in the Docker image. |
| `LEGENDARR_SECRET_KEY` | *(auto-generated)* | Fernet key used to encrypt secrets at rest (`ArrService.api_key` in the database, `*_api_key` fields in `config.yaml`). Leave empty to auto-generate `{LEGENDARR_DATA_DIR}/.secret_key` (owner-only permissions) on first run. Set it explicitly if you need to control the key yourself, e.g. to restore a backup on another host — generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Losing or changing the key makes previously encrypted secrets unreadable. |
| `LEGENDARR_DATABASE_URL` | *(derived from `DATA_DIR`)* | Override the SQLAlchemy database URL used the first time `config.yaml` is created, instead of the default SQLite file. Ignored on later runs — see the note below. |
| `LEGENDARR_RADARR_URL` | *(empty)* | Base URL of your Radarr instance. Leave empty to skip Radarr sync. Ignored once `config.yaml` already has this field — see the note below. |
| `LEGENDARR_RADARR_API_KEY` | *(empty)* | Radarr API key. Same `config.yaml` precedence as `LEGENDARR_RADARR_URL`. |
| `LEGENDARR_SONARR_URL` | *(empty)* | Base URL of your Sonarr instance. Leave empty to skip Sonarr sync. Same `config.yaml` precedence as `LEGENDARR_RADARR_URL`. |
| `LEGENDARR_SONARR_API_KEY` | *(empty)* | Sonarr API key. Same `config.yaml` precedence as `LEGENDARR_RADARR_URL`. |
| `LEGENDARR_SYNC_INTERVAL_MINUTES` | `15` | How often the background scheduler resyncs the media library. Same `config.yaml` precedence as `LEGENDARR_RADARR_URL`. |
| `LEGENDARR_BACKEND_API_URL` | `http://127.0.0.1:8000/api` | Base URL `legendarr_web` uses to call `legendarr_backend`'s API. Only relevant when running `legendarr_web` standalone against a separately-hosted backend — the default is correct for the normal `legendarr_bootstrap` single-process deploy. |

!!! note
    If `LEGENDARR_DATABASE_URL` is unset, legendarr resolves it to
    `sqlite:///{LEGENDARR_DATA_DIR}/legendarr.db` and creates `LEGENDARR_DATA_DIR` if it
    doesn't exist.

!!! note
    On first run, legendarr writes `LEGENDARR_DATABASE_URL` (resolved), the Radarr/Sonarr
    connection settings, and the sync interval to `{LEGENDARR_DATA_DIR}/config.yaml`. From
    then on, `config.yaml` — not these env vars — is the source of truth; it's the file the
    Settings feature (0.4.0) will read and rewrite. If a field is later added to `config.yaml`
    on an existing installation whose file predates it (e.g. upgrading from a version that
    only tracked `database_url`), that one field is backfilled from its env var once and the
    file is rewritten — every other field already in the file is left untouched. Database
    schema changes are applied via Alembic migrations (`modules/backend/db/migrations/`), run
    automatically at startup.
