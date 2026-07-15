# Environment Variables Reference

All variables are prefixed with `LEGENDARR_` and read via `legendarr_backend.shared_kernel.config.Settings`.

| Variable | Default | Description |
| --- | --- | --- |
| `LEGENDARR_DATA_DIR` | `./data` | Directory for the SQLite database and other persisted data. Mounted as `/config` in the Docker image. |
| `LEGENDARR_DATABASE_URL` | *(derived from `DATA_DIR`)* | Override the SQLAlchemy database URL instead of using the default SQLite file. |
| `LEGENDARR_RADARR_URL` | *(empty)* | Base URL of your Radarr instance. Leave empty to skip Radarr sync. |
| `LEGENDARR_RADARR_API_KEY` | *(empty)* | Radarr API key. |
| `LEGENDARR_SONARR_URL` | *(empty)* | Base URL of your Sonarr instance. Leave empty to skip Sonarr sync. |
| `LEGENDARR_SONARR_API_KEY` | *(empty)* | Sonarr API key. |
| `LEGENDARR_SYNC_INTERVAL_MINUTES` | `15` | How often the background scheduler resyncs the media library. |

!!! note
    If `LEGENDARR_DATABASE_URL` is unset, legendarr resolves it to
    `sqlite:///{LEGENDARR_DATA_DIR}/legendarr.db` and creates `LEGENDARR_DATA_DIR` if it
    doesn't exist.
