from pydantic import BaseModel


class DirectoryListingRead(BaseModel):
    path: str
    parent: str | None
    directories: list[str]


class LogLineRead(BaseModel):
    text: str
    level: str


class LogLinesRead(BaseModel):
    lines: list[LogLineRead]
