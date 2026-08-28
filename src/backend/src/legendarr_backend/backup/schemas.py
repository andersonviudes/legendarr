from datetime import datetime

from pydantic import BaseModel


class BackupRead(BaseModel):
    """One archive in `data_dir/backups/` — a snapshot of `config.yaml` (plus the Fernet
    key file, when it isn't sourced from `LEGENDARR_SECRET_KEY`) taken at `created_at`
    (ROADMAP.md 0.22.0). Deliberately doesn't cover the SQLite database — see
    `manage_backups.create_backup`.
    """

    filename: str
    created_at: datetime
    size_bytes: int
    secret_key_included: bool


class RestoreResult(BaseModel):
    """The outcome of a restore. Always a success message telling the admin to restart —
    `config.yaml`/the Fernet key are process-cached state (`get_settings`, `get_fernet`,
    the scheduler) that can't be safely swapped out from under the running process."""

    message: str
