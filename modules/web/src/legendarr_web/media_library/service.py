import httpx


async def trigger_sync(client: httpx.AsyncClient) -> dict:
    response = await client.post("/media/sync")
    response.raise_for_status()
    return response.json()
