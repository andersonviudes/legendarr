import httpx


async def get_task_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/tasks")
    response.raise_for_status()
    return response.json()


async def update_task_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/settings/tasks", json=data)
    response.raise_for_status()
    return response.json()
