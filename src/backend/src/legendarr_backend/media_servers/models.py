from typing import Literal

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from legendarr_backend.security.encrypted_string import EncryptedString

MEDIA_SERVER_KINDS = ("plex", "jellyfin")

# Derived from the tuple above rather than hand-duplicated, so the two can't drift apart.
MediaServerKind = Literal[*MEDIA_SERVER_KINDS]


class MediaServerConfig(SQLModel, table=True):
    """Registration/credentials for one of the fixed `MEDIA_SERVER_KINDS`.

    Same fixed-catalog shape as `MetadataProviderConfig`/`SubtitleProviderConfig` (one
    row per kind, seeded at startup). Unlike those, a Plex/Jellyfin connection also
    needs an address — both `base_url` and `token` are required before it's usable, so
    new rows seed `enabled=False` rather than `True`.
    """

    id: int | None = Field(default=None, primary_key=True)
    kind: str = Field(index=True, unique=True)
    enabled: bool = Field(default=False)
    base_url: str | None = Field(default=None)
    token: str | None = Field(default=None, sa_column=Column(EncryptedString))
    connection_verified: bool = Field(default=False)

    @property
    def has_credentials(self) -> bool:
        return bool(self.base_url) and bool(self.token)

    @property
    def is_configured(self) -> bool:
        """Whether the enable toggle should be available at all — both kinds need a
        reachable address and a token to be usable, so this just mirrors
        `has_credentials`."""
        return self.has_credentials
