import httpx


async def list_language_profiles(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/language-profiles/")
    response.raise_for_status()
    return response.json()
