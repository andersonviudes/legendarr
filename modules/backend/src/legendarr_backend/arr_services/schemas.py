from pydantic import BaseModel

from legendarr_backend.arr_services.models import ArrServiceType


class ArrServiceInput(BaseModel):
    name: str
    service_type: ArrServiceType
    enabled: bool = True
    host: str
    port: int
    base_url: str = "/"
    use_ssl: bool = False
    http_timeout_seconds: int = 60
    api_key: str
