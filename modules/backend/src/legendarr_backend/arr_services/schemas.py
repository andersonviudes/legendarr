from pydantic import BaseModel, Field

from legendarr_backend.arr_services.models import ArrServiceType


class ArrServiceInput(BaseModel):
    name: str = Field(min_length=1)
    service_type: ArrServiceType
    enabled: bool = True
    host: str = Field(min_length=1)
    port: int = Field(gt=0, le=65535)
    base_url: str = "/"
    use_ssl: bool = False
    http_timeout_seconds: int = Field(default=60, gt=0)
    api_key: str
    remote_path_prefix: str | None = None
    local_path_prefix: str | None = None


class ArrServiceEnabledInput(BaseModel):
    """Payload for the enable/disable toggle — flips just the `enabled` flag without
    re-sending (or re-validating the reachability of) the whole service."""

    enabled: bool


class ArrServiceRead(BaseModel):
    """Read projection of `ArrService` that omits `api_key`. No HTTP consumer needs the
    raw key back — the web UI never re-displays it — so it never leaves the backend over
    the wire, on the list view or a single record."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    service_type: str
    enabled: bool
    host: str
    port: int
    base_url: str
    use_ssl: bool
    http_timeout_seconds: int
    remote_path_prefix: str | None
    local_path_prefix: str | None
