from urllib.parse import quote

from legendarr_backend.http_client.client import DEFAULT_TIMEOUT, ProviderHttpClient
from legendarr_backend.media_metadata.providers.base import MediaType, MetadataResult

_BASE_URL = "https://api.themoviedb.org/3"
_POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"


class TmdbMetadataProvider:
    """TMDb (The Movie Database) v3 API client.

    Looks the item up by `imdb_id` via TMDb's `/find` endpoint when one is available
    (Radarr always reports it for movies) and falls back to a title search otherwise —
    same two-path shape `TvdbMetadataProvider` uses for `tvdb_id`/title, just keyed on
    `imdb_id` since TMDb has no notion of a `tvdb_id`.

    Unlike TheTVDB (which validates the key on a separate login call) or OMDb (which
    signals a bad key in the response body), TMDb's v3 key rides along as a query
    param on every call and a rejected one only shows up as a 401 on that call — so,
    also unlike the other two providers, nothing here catches `ProviderClientError`
    locally: it's left to propagate out of `fetch()` so `connection_tests.py` can
    describe a real auth failure instead of misreporting it as "nothing found". The
    periodic sync path is unaffected — `fetch_metadata.py`'s `_safe_fetch` already
    wraps every provider's `fetch()` call in a broad except+log.
    """

    name = "TMDb"

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._api_key = api_key
        self._http = ProviderHttpClient("TMDb", _BASE_URL, timeout=timeout)

    def fetch(
        self,
        *,
        media_type: MediaType,
        title: str,
        tvdb_id: int | None,
        imdb_id: str | None,
    ) -> MetadataResult | None:
        entity = "movie" if media_type == "movie" else "tv"
        record_id = self._find_by_imdb_id(entity, imdb_id) if imdb_id else None
        if record_id is None:
            record_id = self._search(entity, title)
        if record_id is None:
            return None
        data = self._http.get_json(f"/{entity}/{record_id}?api_key={self._api_key}")
        return MetadataResult(
            overview=data.get("overview") or None,
            poster_url=_poster_url(data.get("poster_path")),
            year=_parse_year(data.get("release_date") or data.get("first_air_date")),
        )

    def _find_by_imdb_id(self, entity: str, imdb_id: str) -> int | None:
        body = self._http.get_json(
            f"/find/{imdb_id}?api_key={self._api_key}&external_source=imdb_id"
        )
        results = body.get(f"{entity}_results") or []
        return results[0]["id"] if results else None

    def _search(self, entity: str, title: str) -> int | None:
        body = self._http.get_json(f"/search/{entity}?api_key={self._api_key}&query={quote(title)}")
        results = body.get("results") or []
        return results[0]["id"] if results else None

    def close(self) -> None:
        self._http.close()


def _poster_url(poster_path: str | None) -> str | None:
    return f"{_POSTER_BASE_URL}{poster_path}" if poster_path else None


def _parse_year(date: str | None) -> int | None:
    return int(date[:4]) if date and len(date) >= 4 else None
