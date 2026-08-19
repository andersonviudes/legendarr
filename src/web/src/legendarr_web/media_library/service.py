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


async def get_movie(client: httpx.AsyncClient, movie_id: int) -> dict:
    response = await client.get(f"/media/movies/{movie_id}")
    response.raise_for_status()
    return response.json()


async def get_series_item(client: httpx.AsyncClient, series_id: int) -> dict:
    response = await client.get(f"/media/series/{series_id}")
    response.raise_for_status()
    return response.json()


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
