import logging
from urllib.parse import quote

from legendarr_backend.http_client.client import (
    DEFAULT_TIMEOUT,
    ProviderClientError,
    ProviderHttpClient,
)
from legendarr_backend.media_metadata.providers.base import MediaType, MetadataResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.omdbapi.com"


class OmdbMetadataProvider:
    """IMDb-data client backed by the OMDb API (omdbapi.com) — IMDb itself has no free
    public API, so this is the same wrapper Bazarr and most self-hosted media managers
    use to pull IMDb plot/poster/rating data. Registered/labeled as the `"imdb"` kind
    throughout the rest of the codebase; only this client is actually OMDb underneath.
    """

    name = "IMDb"

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._api_key = api_key
        self._http = ProviderHttpClient("IMDb", _BASE_URL, timeout=timeout)

    def fetch(
        self,
        *,
        media_type: MediaType,
        title: str,
        tvdb_id: int | None,
        imdb_id: str | None,
    ) -> MetadataResult | None:
        query = f"i={imdb_id}" if imdb_id else f"t={quote(title)}"
        try:
            body = self._http.get_json(f"/?apikey={self._api_key}&{query}")
        except ProviderClientError:
            logger.exception("OMDb lookup failed for %r", title)
            return None
        if body.get("Response") != "True":
            return None
        return MetadataResult(
            overview=_clean(body.get("Plot")),
            poster_url=_clean(body.get("Poster")),
            year=_parse_year(body.get("Year")),
            imdb_rating=_parse_rating(body.get("imdbRating")),
        )

    def close(self) -> None:
        self._http.close()


def _clean(value: str | None) -> str | None:
    return value if value and value != "N/A" else None


def _parse_year(value: str | None) -> int | None:
    """OMDb reports a series' `Year` as a range (`"1994–2003"`) — only the first 4 digits
    (the start year) are kept, same shape `MetadataResult.year` uses everywhere else."""
    if not value or len(value) < 4:
        return None
    return int(value[:4])


def _parse_rating(value: str | None) -> float | None:
    if not value or value == "N/A":
        return None
    return float(value)
