import httpx


async def get_history(
    client: httpx.AsyncClient,
    *,
    q: str = "",
    category: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    params: dict = {"q": q, "page": page, "page_size": page_size}
    if category:
        params["category"] = category
    response = await client.get("/history", params=params)
    response.raise_for_status()
    return response.json()
