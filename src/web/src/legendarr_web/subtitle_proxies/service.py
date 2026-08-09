import httpx


async def list_subtitle_proxies(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/subtitle-proxies/")
    response.raise_for_status()
    return response.json()


async def get_subtitle_proxy(client: httpx.AsyncClient, proxy_id: int) -> dict:
    response = await client.get(f"/subtitle-proxies/{proxy_id}")
    response.raise_for_status()
    return response.json()


async def create_subtitle_proxy(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.post("/subtitle-proxies/", json=data)
    response.raise_for_status()
    return response.json()


async def update_subtitle_proxy(client: httpx.AsyncClient, proxy_id: int, data: dict) -> dict:
    response = await client.put(f"/subtitle-proxies/{proxy_id}", json=data)
    response.raise_for_status()
    return response.json()


async def delete_subtitle_proxy(client: httpx.AsyncClient, proxy_id: int) -> None:
    response = await client.delete(f"/subtitle-proxies/{proxy_id}")
    response.raise_for_status()


async def set_subtitle_proxy_enabled(
    client: httpx.AsyncClient, proxy_id: int, enabled: bool
) -> dict:
    response = await client.patch(
        f"/subtitle-proxies/{proxy_id}/enabled", json={"enabled": enabled}
    )
    response.raise_for_status()
    return response.json()


async def test_subtitle_proxy(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.post("/subtitle-proxies/test", json=data)
    response.raise_for_status()
    return response.json()
