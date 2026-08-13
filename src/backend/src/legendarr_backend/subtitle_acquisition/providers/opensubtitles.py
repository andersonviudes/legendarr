from pathlib import Path
from urllib.parse import urlencode

from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult

# Same constant `connection_tests.py`'s "Test connection" check uses — owned here since
# this is now the module that does the real, ongoing calling.
OPENSUBTITLES_USER_AGENT = "legendarr (+https://andersonviudes.github.io/legendarr)"

_BASE_URL = "https://api.opensubtitles.com"


class OpenSubtitlesProvider:
    """Real OpenSubtitles `search()`/`download()` backend, built from a
    `SubtitleProviderConfig`. `include_ai_translated`/`include_machine_translated` map
    directly onto the API's own `ai_translated`/`machine_translated` filters — the first
    fields on that config this provider actually reads.
    """

    name = "opensubtitles"

    def __init__(self, config: SubtitleProviderConfig) -> None:
        self._api_key = config.api_key
        self._include_ai_translated = config.include_ai_translated
        self._include_machine_translated = config.include_machine_translated
        self._use_hash = config.use_hash

    def search(
        self,
        title: str,
        language: str,
        *,
        imdb_id: str | None = None,
        moviehash: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        video_path: Path | None = None,
        tvdb_id: int | None = None,
    ) -> list[SubtitleSearchResult]:
        """`moviehash` is only ever sent when this provider's own `use_hash` config is
        on — the caller always offers it when it has one, this is where that setting
        actually takes effect. `season`/`episode` aren't used by this provider's search
        yet — ignored, same as `video_path` and every other kwarg this provider doesn't
        read."""
        params = {
            "query": title,
            "languages": language.lower(),
            "ai_translated": "include" if self._include_ai_translated else "exclude",
            "machine_translated": "include" if self._include_machine_translated else "exclude",
        }
        if imdb_id:
            params["imdb_id"] = imdb_id.removeprefix("tt")
        if moviehash and self._use_hash:
            params["moviehash"] = moviehash
        client = self._client()
        try:
            response = client.get_json(f"/api/v1/subtitles?{urlencode(params)}")
        finally:
            client.close()
        return [
            SubtitleSearchResult(
                release_name=attributes.get("release") or title,
                download_id=str(file["file_id"]),
                language=attributes.get("language", language),
            )
            for entry in response.get("data", [])
            for attributes in [entry["attributes"]]
            for file in attributes.get("files", [])
        ]

    def download(self, result: SubtitleSearchResult) -> str:
        client = self._client()
        try:
            download_info = client.post_json(
                "/api/v1/download", {"file_id": int(result.download_id)}
            )
            response = client.request("GET", download_info["link"], follow_redirects=True)
            if not response.is_success:
                raise ProviderClientError(
                    f"OpenSubtitles download link {download_info['link']} failed with "
                    f"{response.status_code}"
                )
        finally:
            client.close()
        return response.text

    def _client(self) -> ProviderHttpClient:
        return ProviderHttpClient(
            "OpenSubtitles",
            _BASE_URL,
            headers={"Api-Key": self._api_key or "", "User-Agent": OPENSUBTITLES_USER_AGENT},
        )
