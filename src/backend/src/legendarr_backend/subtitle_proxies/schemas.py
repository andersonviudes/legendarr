from pydantic import BaseModel, Field


class SubtitleProxyInput(BaseModel):
    name: str = Field(min_length=1)
    host: str = Field(min_length=1)
    enabled: bool = True


class SubtitleProxyEnabledInput(BaseModel):
    """Payload for the enable/disable toggle — flips just the `enabled` flag without
    re-sending (or re-validating the reachability of) the whole proxy."""

    enabled: bool


class SubtitleProxyRead(BaseModel):
    """Read projection of `SubtitleProxy`. No secrets on this model, so unlike
    `SubtitleProviderConfigRead` there's nothing to omit — this mirrors the model 1:1."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    host: str
    enabled: bool
