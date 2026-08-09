import httpx


async def list_metadata_providers(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/metadata-providers/")
    response.raise_for_status()
    return response.json()


async def get_metadata_provider(client: httpx.AsyncClient, provider_id: int) -> dict:
    response = await client.get(f"/metadata-providers/{provider_id}")
    response.raise_for_status()
    return response.json()


async def update_metadata_provider(client: httpx.AsyncClient, provider_id: int, data: dict) -> dict:
    response = await client.patch(f"/metadata-providers/{provider_id}", json=data)
    response.raise_for_status()
    return response.json()


async def set_metadata_provider_enabled(
    client: httpx.AsyncClient, provider_id: int, enabled: bool
) -> dict:
    response = await client.patch(f"/metadata-providers/{provider_id}", json={"enabled": enabled})
    response.raise_for_status()
    return response.json()


async def test_metadata_provider(client: httpx.AsyncClient, provider_id: int, data: dict) -> dict:
    response = await client.post(f"/metadata-providers/{provider_id}/test", json=data)
    response.raise_for_status()
    return response.json()
