from pydantic import BaseModel


class MetadataProviderConfigInput(BaseModel):
    enabled: bool = True
    api_key: str | None = None


class MetadataProviderConfigRead(BaseModel):
    """Read projection of `MetadataProviderConfig` that omits `api_key` — no HTTP
    consumer needs the raw secret back, the web UI never re-displays it."""

    model_config = {"from_attributes": True}

    id: int
    kind: str
    enabled: bool
    is_configured: bool
