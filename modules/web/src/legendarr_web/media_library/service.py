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
