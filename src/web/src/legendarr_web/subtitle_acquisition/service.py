import httpx


async def list_subtitle_providers(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/subtitle-providers/")
    response.raise_for_status()
    return response.json()


async def get_subtitle_provider(client: httpx.AsyncClient, provider_id: int) -> dict:
    response = await client.get(f"/subtitle-providers/{provider_id}")
    response.raise_for_status()
    return response.json()


async def update_subtitle_provider(client: httpx.AsyncClient, provider_id: int, data: dict) -> dict:
    response = await client.patch(f"/subtitle-providers/{provider_id}", json=data)
    response.raise_for_status()
    return response.json()


async def set_subtitle_provider_enabled(
    client: httpx.AsyncClient, provider_id: int, enabled: bool
) -> dict:
    response = await client.patch(f"/subtitle-providers/{provider_id}", json={"enabled": enabled})
    response.raise_for_status()
    return response.json()


async def test_subtitle_provider(client: httpx.AsyncClient, provider_id: int, data: dict) -> dict:
    response = await client.post(f"/subtitle-providers/{provider_id}/test", json=data)
    response.raise_for_status()
    return response.json()
