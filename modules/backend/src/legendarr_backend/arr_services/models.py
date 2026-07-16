from typing import Literal

from sqlmodel import Field, SQLModel

ArrServiceType = Literal["radarr", "sonarr"]


class ArrService(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    service_type: str
    enabled: bool = Field(default=True)
    host: str
    port: int
    base_url: str = Field(default="/")
    use_ssl: bool = Field(default=False)
    http_timeout_seconds: int = Field(default=60)
    api_key: str
