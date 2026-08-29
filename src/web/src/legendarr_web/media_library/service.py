import asyncio

import httpx


async def trigger_sync(client: httpx.AsyncClient) -> dict:
    response = await client.post("/media/sync")
    response.raise_for_status()
    return response.json()


async def list_movies(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/media/movies")
    response.raise_for_status()
    return response.json()


async def list_series(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/media/series")
    response.raise_for_status()
    return response.json()


async def list_wanted(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/media/wanted")
    response.raise_for_status()
    return response.json()


async def search_media(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Case-insensitive title search across synced movies and series, for the topbar
    search dropdown — capped to a handful of results."""
    needle = query.lower()
    movies = await list_movies(client)
    series = await list_series(client)
    matches = [
        {"id": movie["id"], "title": movie["title"], "type": "movie"}
        for movie in movies
        if needle in movie["title"].lower()
    ]
    matches += [
        {"id": item["id"], "title": item["title"], "type": "series"}
        for item in series
        if needle in item["title"].lower()
    ]
    return matches[:8]


async def get_movie(client: httpx.AsyncClient, movie_id: int) -> dict:
    response = await client.get(f"/media/movies/{movie_id}")
    response.raise_for_status()
    return response.json()


async def get_series_item(client: httpx.AsyncClient, series_id: int) -> dict:
    response = await client.get(f"/media/series/{series_id}")
    response.raise_for_status()
    return response.json()


async def ensure_poster_cached(client: httpx.AsyncClient, item: dict, media_type: str) -> None:
    """On-demand fallback (ROADMAP.md 0.20.0): if `item` has a `poster_url` but isn't
    cached on disk yet, ask the backend to fetch-and-cache it right now instead of
    showing nothing while the periodic refresh job hasn't gotten to it yet.
    Best-effort — a failed backend call just leaves the item without a poster, same as
    before this existed."""
    if not item.get("poster_url") or item.get("poster_cached"):
        return
    kind = "movies" if media_type == "movie" else "series"
    try:
        response = await client.post(f"/media/{kind}/{item['id']}/poster-cache")
        response.raise_for_status()
        item["poster_cached"] = response.json()["cached"]
    except (httpx.HTTPError, KeyError, ValueError):
        pass


async def ensure_posters_cached(
    client: httpx.AsyncClient, items: list[dict], media_type: str
) -> None:
    """Runs `ensure_poster_cached` for every item in `items` concurrently, so a list
    page with several uncached posters isn't gated on them one at a time."""
    await asyncio.gather(*(ensure_poster_cached(client, item, media_type) for item in items))


async def ensure_wanted_posters_cached(client: httpx.AsyncClient, items: list[dict]) -> None:
    """Same as `ensure_posters_cached`, for the wanted list where movies and series are
    mixed together — each item's own `kind` picks its poster-cache route."""
    await asyncio.gather(*(ensure_poster_cached(client, item, item["kind"]) for item in items))


async def trigger_movie_scan(client: httpx.AsyncClient, movie_id: int) -> dict:
    response = await client.post(f"/media/movies/{movie_id}/scan")
    response.raise_for_status()
    return response.json()


async def trigger_series_scan(client: httpx.AsyncClient, series_id: int) -> dict:
    response = await client.post(f"/media/series/{series_id}/scan")
    response.raise_for_status()
    return response.json()


async def trigger_file_translation(client: httpx.AsyncClient, media_file_id: int) -> dict:
    response = await client.post(f"/media/files/{media_file_id}/translate")
    response.raise_for_status()
    return response.json()


async def trigger_subtitle_timing_sync(client: httpx.AsyncClient, subtitle_id: int) -> dict:
    response = await client.post(f"/media/subtitles/{subtitle_id}/sync-timing")
    response.raise_for_status()
    return response.json()


async def trigger_subtitle_translation(client: httpx.AsyncClient, subtitle_id: int) -> dict:
    response = await client.post(f"/media/subtitles/{subtitle_id}/translate")
    response.raise_for_status()
    return response.json()


async def blacklist_subtitle(client: httpx.AsyncClient, subtitle_id: int) -> dict:
    response = await client.post(f"/media/subtitles/{subtitle_id}/blacklist")
    response.raise_for_status()
    return response.json()


async def remove_subtitle_style_tags(client: httpx.AsyncClient, subtitle_id: int) -> dict:
    response = await client.post(f"/media/subtitles/{subtitle_id}/remove-style-tags")
    response.raise_for_status()
    return response.json()


async def get_target_languages(client: httpx.AsyncClient, media_file_id: int) -> list[str]:
    response = await client.get(f"/media/files/{media_file_id}/target-languages")
    response.raise_for_status()
    return response.json()


async def search_subtitle_candidates(
    client: httpx.AsyncClient, media_file_id: int, language: str
) -> list[dict]:
    response = await client.get(
        f"/media/files/{media_file_id}/subtitle-candidates", params={"language": language}
    )
    response.raise_for_status()
    return response.json()


async def download_subtitle_candidate(
    client: httpx.AsyncClient, media_file_id: int, candidate: dict
) -> dict:
    response = await client.post(
        f"/media/files/{media_file_id}/subtitle-candidates/download", json=candidate
    )
    response.raise_for_status()
    return response.json()


async def upload_subtitle(
    client: httpx.AsyncClient,
    media_file_id: int,
    language: str,
    filename: str,
    content: bytes,
) -> dict:
    response = await client.post(
        f"/media/files/{media_file_id}/subtitle-upload",
        data={"language": language},
        files={"file": (filename, content)},
    )
    response.raise_for_status()
    return response.json()


def _pending_episode_path(series_id: int, season_number: int, episode_number: int) -> str:
    return f"/media/series/{series_id}/episodes/{season_number}/{episode_number}"


async def get_pending_episode_target_languages(
    client: httpx.AsyncClient, series_id: int, season_number: int, episode_number: int
) -> list[str]:
    response = await client.get(
        f"{_pending_episode_path(series_id, season_number, episode_number)}/target-languages"
    )
    response.raise_for_status()
    return response.json()


async def search_pending_subtitle_candidates(
    client: httpx.AsyncClient,
    series_id: int,
    season_number: int,
    episode_number: int,
    language: str,
) -> list[dict]:
    response = await client.get(
        f"{_pending_episode_path(series_id, season_number, episode_number)}/subtitle-candidates",
        params={"language": language},
    )
    response.raise_for_status()
    return response.json()


async def download_pending_subtitle_candidate(
    client: httpx.AsyncClient,
    series_id: int,
    season_number: int,
    episode_number: int,
    candidate: dict,
) -> dict:
    response = await client.post(
        f"{_pending_episode_path(series_id, season_number, episode_number)}"
        "/subtitle-candidates/download",
        json=candidate,
    )
    response.raise_for_status()
    return response.json()


async def upload_pending_subtitle(
    client: httpx.AsyncClient,
    series_id: int,
    season_number: int,
    episode_number: int,
    language: str,
    filename: str,
    content: bytes,
) -> dict:
    response = await client.post(
        f"{_pending_episode_path(series_id, season_number, episode_number)}/subtitle-upload",
        data={"language": language},
        files={"file": (filename, content)},
    )
    response.raise_for_status()
    return response.json()
