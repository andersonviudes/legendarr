import httpx


async def list_language_profiles(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/language-profiles/")
    response.raise_for_status()
    return response.json()


async def get_language_profile(client: httpx.AsyncClient, profile_id: int) -> dict:
    response = await client.get(f"/language-profiles/{profile_id}")
    response.raise_for_status()
    return response.json()


async def create_language_profile(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.post("/language-profiles/", json=data)
    response.raise_for_status()
    return response.json()


async def update_language_profile(client: httpx.AsyncClient, profile_id: int, data: dict) -> dict:
    response = await client.put(f"/language-profiles/{profile_id}", json=data)
    response.raise_for_status()
    return response.json()


async def delete_language_profile(client: httpx.AsyncClient, profile_id: int) -> None:
    response = await client.delete(f"/language-profiles/{profile_id}")
    response.raise_for_status()
