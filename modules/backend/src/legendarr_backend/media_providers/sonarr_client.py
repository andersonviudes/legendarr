from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class SeriesFile:
    """A single series tracked by a Sonarr instance."""

    id: int
    title: str
    path: str


class SonarrClient:
    """Thin client over the Sonarr v3 API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-Api-Key": api_key},
            timeout=10.0,
        )

    def list_series(self) -> list[SeriesFile]:
        response = self._client.get("/api/v3/series")
        response.raise_for_status()
        return [
            SeriesFile(id=item["id"], title=item["title"], path=item.get("path", ""))
            for item in response.json()
        ]

    def close(self) -> None:
        self._client.close()
