import httpx


async def login(
    client: httpx.AsyncClient, username: str, password: str, *, ip_address: str, user_agent: str
) -> dict:
    response = await client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
            "ip_address": ip_address,
            "user_agent": user_agent,
        },
    )
    response.raise_for_status()
    return response.json()


async def logout(client: httpx.AsyncClient, token: str | None) -> None:
    response = await client.post("/auth/logout", json={"token": token})
    response.raise_for_status()


async def validate_session(
    client: httpx.AsyncClient, token: str | None, *, ip_address: str, user_agent: str
) -> dict:
    response = await client.post(
        "/auth/sessions/validate",
        json={"token": token, "ip_address": ip_address, "user_agent": user_agent},
    )
    response.raise_for_status()
    return response.json()
