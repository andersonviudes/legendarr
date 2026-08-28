import httpx


async def get_statistics(client: httpx.AsyncClient) -> dict:
    response = await client.get("/statistics")
    response.raise_for_status()
    return response.json()
