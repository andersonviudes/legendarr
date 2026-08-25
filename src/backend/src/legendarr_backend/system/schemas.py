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
