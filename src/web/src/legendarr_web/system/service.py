import httpx


async def get_recent_logs(client: httpx.AsyncClient, level: str | None = None) -> list[dict]:
    params = {"level": level} if level else {}
    response = await client.get("/system/logs", params=params)
    response.raise_for_status()
    return response.json()


async def browse_directory(client: httpx.AsyncClient, path: str) -> dict:
    response = await client.get("/system/directories", params={"path": path})
    response.raise_for_status()
    return response.json()


async def get_running_tasks(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/system/tasks/running")
    response.raise_for_status()
    return response.json()
