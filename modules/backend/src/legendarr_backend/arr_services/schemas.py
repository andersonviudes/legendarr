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


class ArrServiceSummary(BaseModel):
    """List-view projection of `ArrService` that omits `api_key` — the list page never
    needs the raw key, so there's no reason to ship it over the wire for every row."""

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
