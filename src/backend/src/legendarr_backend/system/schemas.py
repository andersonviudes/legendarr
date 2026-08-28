from datetime import datetime

from pydantic import BaseModel


class DirectoryListingRead(BaseModel):
    path: str
    parent: str | None
    directories: list[str]


class LogLineRead(BaseModel):
    text: str
    level: str


class RunningTaskRead(BaseModel):
    job_id: str
    name: str
    queue: str
    started_at: datetime
    phase: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    language: str | None = None
    provider: str | None = None


class ScheduledJobRead(BaseModel):
    job_id: str
    name: str
    queue: str
    trigger: str
    next_run_time: datetime | None


class JobRunRead(BaseModel):
    job_id: str
    name: str
    queue: str
    status: str
    started_at: datetime
    finished_at: datetime
    error_message: str | None
