import httpx


async def list_translation_providers(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/translation-providers/")
    response.raise_for_status()
    return response.json()


async def get_translation_provider(client: httpx.AsyncClient, provider_id: int) -> dict:
    response = await client.get(f"/translation-providers/{provider_id}")
    response.raise_for_status()
    return response.json()


async def update_translation_provider(
    client: httpx.AsyncClient, provider_id: int, data: dict
) -> dict:
    response = await client.patch(f"/translation-providers/{provider_id}", json=data)
    response.raise_for_status()
    return response.json()


async def set_translation_provider_enabled(
    client: httpx.AsyncClient, provider_id: int, enabled: bool
) -> dict:
    response = await client.patch(
        f"/translation-providers/{provider_id}", json={"enabled": enabled}
    )
    response.raise_for_status()
    return response.json()


async def test_translation_provider(
    client: httpx.AsyncClient, provider_id: int, data: dict
) -> dict:
    response = await client.post(f"/translation-providers/{provider_id}/test", json=data)
    response.raise_for_status()
    return response.json()


async def get_translation_defaults(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/translation-defaults")
    response.raise_for_status()
    return response.json()


async def set_default_translation_provider(client: httpx.AsyncClient, kind: str) -> dict:
    response = await client.put(
        "/settings/translation-defaults", json={"default_translation_provider": kind}
    )
    response.raise_for_status()
    return response.json()
