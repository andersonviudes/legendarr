from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.providers.radarr_client import RadarrClient
from legendarr_backend.media_library.providers.sonarr_client import SonarrClient


def build_base_url(host: str, port: int, base_url: str, use_ssl: bool) -> str:
    scheme = "https" if use_ssl else "http"
    path = base_url if base_url.startswith("/") else f"/{base_url}"
    return f"{scheme}://{host}:{port}{path}".rstrip("/")


def build_client(data: ArrServiceInput) -> RadarrClient | SonarrClient:
    base_url = build_base_url(data.host, data.port, data.base_url, data.use_ssl)
    client_cls = RadarrClient if data.service_type == "radarr" else SonarrClient
    return client_cls(base_url, data.api_key, timeout=data.http_timeout_seconds)
