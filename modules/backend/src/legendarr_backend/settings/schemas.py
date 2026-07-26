from pydantic import BaseModel, Field


class TaskSettings(BaseModel):
    """Runtime-tunable parameters of the three scheduled tasks.

    Mirrors the task-related fields of `AppConfigFile` with added bounds — this is
    the only shape the `/settings/tasks` endpoints accept and return, so bootstrap
    fields (`database_url`, legacy `radarr_*`) are never exposed here.
    """

    sync_interval_minutes: int = Field(gt=0)
    sync_retry_attempts: int = Field(ge=1)
    sync_retry_delay_seconds: float = Field(ge=0)
    sync_max_instances: int = Field(ge=1)
    sync_coalesce: bool
    scan_interval_minutes: int = Field(gt=0)
    scan_retry_attempts: int = Field(ge=1)
    scan_retry_delay_seconds: float = Field(ge=0)
    scan_max_instances: int = Field(ge=1)
    scan_coalesce: bool
    history_poll_interval_minutes: int = Field(gt=0)
    history_poll_retry_attempts: int = Field(ge=1)
    history_poll_retry_delay_seconds: float = Field(ge=0)
    history_poll_max_instances: int = Field(ge=1)
    history_poll_coalesce: bool
