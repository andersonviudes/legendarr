from pydantic import BaseModel, Field


class SubtitleProviderConfigInput(BaseModel):
    enabled: bool = True
    api_key: str | None = None
    username: str | None = None
    password: str | None = None
    proxy_id: int | None = None
    # Defaults mirror the model's (and Bazarr's) — unlike the secrets above, `None` isn't a
    # valid value for these columns, so a direct (router-bypassing) call with them omitted
    # must fall back to a real bool, not `None`. `_merge_with_existing` still preserves the
    # stored value on a partial PATCH by checking `model_fields_set`, not this default.
    use_hash: bool = True
    include_ai_translated: bool = False
    include_machine_translated: bool = False


class SubtitleProviderConfigRead(BaseModel):
    """Read projection of `SubtitleProviderConfig` that omits `api_key` and `password`.
    No HTTP consumer needs the raw secrets back — the web UI never re-displays them — so
    they never leave the backend over the wire, on the list view or a single record.
    """

    model_config = {"from_attributes": True}

    id: int
    kind: str
    enabled: bool
    username: str | None
    is_configured: bool
    proxy_id: int | None
    use_hash: bool
    include_ai_translated: bool
    include_machine_translated: bool


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
