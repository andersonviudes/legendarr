from sqlmodel import Field, SQLModel


class SubtitleProxy(SQLModel, table=True):
    """A user-registered indexer-style proxy (e.g. FlareSolverr) a `SubtitleProviderConfig`
    can be pointed at to get past a CAPTCHA/Cloudflare wall.

    User-created and arbitrary in count, unlike `SubtitleProviderConfig`'s fixed, seeded
    catalog — mirrors `ArrService`'s shape instead. `host` is stored as a full base URL
    (e.g. `http://10.0.1.1:8191/`), not split into host/port/use_ssl like `ArrService`, since
    that's the single field FlareSolverr (and any future proxy kind) needs.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    host: str
    enabled: bool = Field(default=True)
