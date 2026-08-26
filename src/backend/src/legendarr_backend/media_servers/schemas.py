from pydantic import BaseModel


class MediaServerConfigInput(BaseModel):
    enabled: bool = False
    base_url: str | None = None
    token: str | None = None


class MediaServerConfigRead(BaseModel):
    """Read projection of `MediaServerConfig` that omits `token` — no HTTP consumer
    needs the raw secret back, the web UI never re-displays it."""

    model_config = {"from_attributes": True}

    id: int
    kind: str
    enabled: bool
    base_url: str | None
    is_configured: bool
