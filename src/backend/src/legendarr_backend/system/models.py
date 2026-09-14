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
    # "success" | "failure" | "missed" — all three recorded from APScheduler's own events
    # — plus "abandoned", recorded by `system/job_history.record_abandoned_run` for a run
    # that never reported an outcome at all and had to be swept out of the running-task
    # registry (`maintenance/reap_stuck_tasks.py`).
    status: str
    started_at: datetime
    finished_at: datetime = Field(index=True)
    error_message: str | None = Field(default=None)
