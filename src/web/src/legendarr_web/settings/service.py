import httpx


async def get_task_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/tasks")
    response.raise_for_status()
    return response.json()


async def update_task_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/settings/tasks", json=data)
    response.raise_for_status()
    return response.json()


async def get_auth_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/auth/settings")
    response.raise_for_status()
    return response.json()


async def update_auth_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/auth/settings", json=data)
    response.raise_for_status()
    return response.json()


async def regenerate_api_key(client: httpx.AsyncClient) -> dict:
    response = await client.post("/auth/settings/api-key/regenerate")
    response.raise_for_status()
    return response.json()


async def get_general_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/general")
    response.raise_for_status()
    return response.json()


async def update_general_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/settings/general", json=data)
    response.raise_for_status()
    return response.json()


async def get_webhook_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/webhooks")
    response.raise_for_status()
    return response.json()


async def update_webhook_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/settings/webhooks", json=data)
    response.raise_for_status()
    return response.json()
