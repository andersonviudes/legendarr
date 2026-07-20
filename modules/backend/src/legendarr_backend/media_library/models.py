from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Movie(SQLModel, table=True):
    """A movie tracked by one of the configured Radarr connections.

    `remote_path` is stored exactly as Radarr reports it — path translation to the
    local filesystem happens at read time via the connection's path mapping, so
    editing the mapping never requires a re-sync.
    """

    __table_args__ = (UniqueConstraint("arr_service_id", "arr_id"),)

    id: int | None = Field(default=None, primary_key=True)
    arr_service_id: int = Field(foreign_key="arrservice.id", index=True)
    arr_id: int
    title: str
    remote_path: str
    # Pins this movie to a profile other than whichever one is marked `is_default` —
    # nullable, so most rows fall back to the default instead of needing an explicit link.
    language_profile_id: int | None = Field(
        default=None, foreign_key="languageprofile.id", index=True
    )


class Series(SQLModel, table=True):
    """A series tracked by one of the configured Sonarr connections.

    Same storage contract as `Movie`: the path is kept as Sonarr reports it.
    """

    __table_args__ = (UniqueConstraint("arr_service_id", "arr_id"),)

    id: int | None = Field(default=None, primary_key=True)
    arr_service_id: int = Field(foreign_key="arrservice.id", index=True)
    arr_id: int
    title: str
    remote_path: str
    language_profile_id: int | None = Field(
        default=None, foreign_key="languageprofile.id", index=True
    )
