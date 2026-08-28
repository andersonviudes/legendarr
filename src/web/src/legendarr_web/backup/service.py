import httpx


async def list_backups(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/backup/")
    response.raise_for_status()
    return response.json()


async def create_backup(client: httpx.AsyncClient) -> dict:
    response = await client.post("/backup/")
    response.raise_for_status()
    return response.json()


async def delete_backup(client: httpx.AsyncClient, filename: str) -> None:
    response = await client.delete(f"/backup/{filename}")
    response.raise_for_status()


async def download_backup(client: httpx.AsyncClient, filename: str) -> httpx.Response:
    response = await client.get(f"/backup/{filename}/download")
    response.raise_for_status()
    return response


async def restore_backup(client: httpx.AsyncClient, filename: str, content: bytes) -> dict:
    response = await client.post("/backup/restore", files={"file": (filename, content)})
    response.raise_for_status()
    return response.json()


async def get_backup_settings(client: httpx.AsyncClient) -> dict:
    response = await client.get("/settings/backup-retention")
    response.raise_for_status()
    return response.json()


async def update_backup_settings(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.put("/settings/backup-retention", json=data)
    response.raise_for_status()
    return response.json()
