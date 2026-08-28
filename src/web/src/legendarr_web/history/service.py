import httpx


async def get_history(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/history")
    response.raise_for_status()
    return response.json()
