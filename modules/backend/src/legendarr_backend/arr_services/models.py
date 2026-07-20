from typing import Literal

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from legendarr_backend.security.encrypted_string import EncryptedString

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
    api_key: str = Field(sa_column=Column(EncryptedString, nullable=False))
