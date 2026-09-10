import httpx


async def get_history(
    client: httpx.AsyncClient, *, q: str = "", page: int = 1, page_size: int = 25
) -> dict:
    response = await client.get("/history", params={"q": q, "page": page, "page_size": page_size})
    response.raise_for_status()
    return response.json()
