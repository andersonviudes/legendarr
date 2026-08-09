from pydantic import BaseModel


class TranslationProviderConfigInput(BaseModel):
    enabled: bool = True
    api_key: str | None = None
    endpoint: str | None = None


class TranslationProviderConfigRead(BaseModel):
    """Read projection of `TranslationProviderConfig` that omits `api_key`. No HTTP consumer
    needs the raw secret back — the web UI never re-displays it — so it never leaves the
    backend over the wire, on the list view or a single record.
    """

    model_config = {"from_attributes": True}

    id: int
    kind: str
    enabled: bool
    endpoint: str | None
    is_configured: bool
