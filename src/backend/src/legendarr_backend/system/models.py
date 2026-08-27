from datetime import datetime

from sqlmodel import Field, SQLModel


class JobRun(SQLModel, table=True):
    """One row per completed scheduler job execution — the System page's post-mortem
    job history. Unlike `RunningTaskRegistry` (`scheduling/running_tasks.py`), which only
    tracks jobs still in flight and resets on restart, this persists so a job's outcome
    survives past a restart.

    `started_at` is the job's *scheduled* run time (APScheduler's `scheduled_run_time`)
    rather than the actual dispatch time — close enough for a monitoring view, and avoids
    correlating against the separate in-flight registry just for this.
    """

    id: int | None = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    name: str
    queue: str
    status: str  # "success" | "failure" | "missed"
    started_at: datetime
    finished_at: datetime = Field(index=True)
    error_message: str | None = Field(default=None)
