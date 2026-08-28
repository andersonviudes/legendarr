import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _history_entry(**overrides) -> dict:
    entry = {
        "category": "translation",
        "status": "success",
        "media_title": "Foo",
        "language": "pt-BR",
        "provider": "deepl",
        "error_message": None,
        "occurred_at": "2026-08-28T10:00:00",
        "score": None,
    }
    entry.update(overrides)
    return entry


def test_history_page_shows_recorded_entries(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                _history_entry(),
                _history_entry(
                    category="acquisition",
                    status="failure",
                    media_title="Bar",
                    language="en",
                    provider=None,
                    error_message="opensubtitles: 401 Unauthorized",
                ),
                _history_entry(
                    category="acquisition",
                    status="success",
                    media_title="Baz",
                    language="en",
                    provider="opensubtitles",
                    score=0.9,
                ),
            ],
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/")

    assert response.status_code == 200
    assert "Foo" in response.text
    assert "deepl" in response.text
    assert "Bar" in response.text
    assert "opensubtitles: 401 Unauthorized" in response.text
    assert "Baz" in response.text
    assert "90%" in response.text


def test_history_page_shows_empty_state_with_no_activity(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/")

    assert response.status_code == 200
    assert "No translation or acquisition activity yet" in response.text
