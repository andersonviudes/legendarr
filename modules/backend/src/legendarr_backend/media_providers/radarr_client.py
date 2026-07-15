from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class MediaFile:
    """A single movie tracked by a Radarr instance."""

    id: int
    title: str
    path: str


class RadarrClient:
    """Thin client over the Radarr v3 API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-Api-Key": api_key},
            timeout=10.0,
        )

    def list_movies(self) -> list[MediaFile]:
        response = self._client.get("/api/v3/movie")
        response.raise_for_status()
        return [
            MediaFile(id=item["id"], title=item["title"], path=item.get("path", ""))
            for item in response.json()
        ]

    def close(self) -> None:
        self._client.close()
