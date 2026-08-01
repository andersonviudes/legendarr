import logging
from urllib.parse import quote

from legendarr_backend.http_client.client import (
    DEFAULT_TIMEOUT,
    ProviderClientError,
    ProviderHttpClient,
)
from legendarr_backend.media_metadata.providers.base import MediaType, MetadataResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://api4.thetvdb.com/v4"


class TvdbMetadataProvider:
    """TheTVDB v4 API client.

    Logs in lazily on the first `fetch()` call (API-key-only, non-subscriber flow — no
    `pin`) and reuses the resulting bearer token for the rest of this instance's life.
    Build one instance per sync run, not per item, so a single login covers every new
    item that sync finds.

    Radarr never reports a `tvdb_id` for movies (its own canonical id system is TMDb),
    so a movie fetch falls back to a title search; a series fetch always has Sonarr's
    own `tvdbId` and looks the record up directly.
    """

    name = "TheTVDB"

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._http: ProviderHttpClient | None = None

    def fetch(
        self,
        *,
        media_type: MediaType,
        title: str,
        tvdb_id: int | None,
        imdb_id: str | None,
    ) -> MetadataResult | None:
        self._ensure_logged_in()
        entity = "movies" if media_type == "movie" else "series"
        record_id = tvdb_id or self._search(entity, title)
        if record_id is None:
            return None
        try:
            body = self._http.get_json(f"/{entity}/{record_id}/extended")
        except ProviderClientError:
            logger.exception("TheTVDB lookup failed for %r", title)
            return None
        data = body.get("data") or {}
        return MetadataResult(
            overview=data.get("overview"),
            poster_url=data.get("image"),
            year=_parse_year(data),
        )

    def _ensure_logged_in(self) -> None:
        if self._http is not None:
            return
        login_client = ProviderHttpClient("TheTVDB", _BASE_URL, timeout=self._timeout)
        try:
            body = login_client.post_json("/login", {"apikey": self._api_key})
        finally:
            login_client.close()
        token = body["data"]["token"]
        self._http = ProviderHttpClient(
            "TheTVDB",
            _BASE_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=self._timeout,
        )

    def _search(self, entity: str, title: str) -> int | None:
        entity_type = "movie" if entity == "movies" else "series"
        try:
            body = self._http.get_json(f"/search?query={quote(title)}&type={entity_type}")
        except ProviderClientError:
            logger.exception("TheTVDB search failed for %r", title)
            return None
        results = body.get("data") or []
        if not results:
            return None
        record_id = results[0].get("tvdb_id")
        return int(record_id) if record_id else None

    def close(self) -> None:
        if self._http is not None:
            self._http.close()


def _parse_year(data: dict) -> int | None:
    """`year` is a plain field on a movie record; a series record only has
    `firstAired` (an ISO date), so fall back to its leading 4 digits."""
    year = data.get("year")
    if year:
        return int(year)
    first_aired = data.get("firstAired")
    if first_aired and len(first_aired) >= 4:
        return int(first_aired[:4])
    return None
