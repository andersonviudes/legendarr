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


async def get_scheduled_jobs(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/system/jobs/scheduled")
    response.raise_for_status()
    return response.json()


async def get_job_history(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/system/jobs/history")
    response.raise_for_status()
    return response.json()


async def get_provider_health(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/system/providers")
    response.raise_for_status()
    return response.json()


async def get_sessions(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get("/auth/sessions")
    response.raise_for_status()
    return response.json()


async def revoke_session(client: httpx.AsyncClient, session_id: int) -> None:
    response = await client.delete(f"/auth/sessions/{session_id}")
    response.raise_for_status()


async def revoke_other_sessions(client: httpx.AsyncClient, keep_session_id: int) -> dict:
    response = await client.post(
        "/auth/sessions/revoke-others", json={"keep_session_id": keep_session_id}
    )
    response.raise_for_status()
    return response.json()
