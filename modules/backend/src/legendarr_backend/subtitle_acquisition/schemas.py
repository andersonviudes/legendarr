from pydantic import BaseModel


class SubtitleProviderConfigInput(BaseModel):
    enabled: bool = True
    api_key: str | None = None
    username: str | None = None
    password: str | None = None
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
    use_hash: bool
    include_ai_translated: bool
    include_machine_translated: bool
