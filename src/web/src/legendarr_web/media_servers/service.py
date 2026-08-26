import httpx


async def list_media_servers(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/media-servers/")
    response.raise_for_status()
    return response.json()


async def get_media_server(client: httpx.AsyncClient, server_id: int) -> dict:
    response = await client.get(f"/media-servers/{server_id}")
    response.raise_for_status()
    return response.json()


async def update_media_server(client: httpx.AsyncClient, server_id: int, data: dict) -> dict:
    response = await client.patch(f"/media-servers/{server_id}", json=data)
    response.raise_for_status()
    return response.json()


async def set_media_server_enabled(
    client: httpx.AsyncClient, server_id: int, enabled: bool
) -> dict:
    response = await client.patch(f"/media-servers/{server_id}", json={"enabled": enabled})
    response.raise_for_status()
    return response.json()


async def test_media_server(client: httpx.AsyncClient, server_id: int, data: dict) -> dict:
    response = await client.post(f"/media-servers/{server_id}/test", json=data)
    response.raise_for_status()
    return response.json()
