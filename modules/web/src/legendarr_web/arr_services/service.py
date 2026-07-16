import httpx


async def list_arr_services(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/arr-services/")
    response.raise_for_status()
    return response.json()


async def get_arr_service(client: httpx.AsyncClient, service_id: int) -> dict:
    response = await client.get(f"/arr-services/{service_id}")
    response.raise_for_status()
    return response.json()


async def create_arr_service(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.post("/arr-services/", json=data)
    response.raise_for_status()
    return response.json()


async def update_arr_service(client: httpx.AsyncClient, service_id: int, data: dict) -> dict:
    response = await client.put(f"/arr-services/{service_id}", json=data)
    response.raise_for_status()
    return response.json()


async def delete_arr_service(client: httpx.AsyncClient, service_id: int) -> None:
    response = await client.delete(f"/arr-services/{service_id}")
    response.raise_for_status()


async def test_arr_service(client: httpx.AsyncClient, data: dict) -> dict:
    response = await client.post("/arr-services/test", json=data)
    response.raise_for_status()
    return response.json()
