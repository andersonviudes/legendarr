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
        "previous_score": None,
    }
    entry.update(overrides)
    return entry


def _history_page(entries: list[dict], *, total: int | None = None, page: int = 1) -> dict:
    return {
        "entries": entries,
        "total": total if total is not None else len(entries),
        "page": page,
        "page_size": 25,
    }


def test_history_page_shows_recorded_entries(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_history_page(
                [
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
                    _history_entry(
                        category="upgrade",
                        status="success",
                        media_title="Qux",
                        language="en",
                        provider="opensubtitles",
                        score=0.8,
                        previous_score=0.45,
                    ),
                ]
            ),
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
    assert "Qux" in response.text
    assert "45% → 80%" in response.text


def test_history_page_shows_empty_state_with_no_activity(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_history_page([]))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/")

    assert response.status_code == 200
    assert "No translation or acquisition activity yet" in response.text


def test_history_page_search_input_echoes_the_query(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_history_page([_history_entry()]))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/", params={"q": "deepl"})

    assert response.status_code == 200
    assert 'value="deepl"' in response.text


def test_history_page_shows_search_no_results_state(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_history_page([]))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/", params={"q": "nonexistent"})

    assert response.status_code == 200
    assert "No history entries match your search" in response.text


def test_history_page_shows_pagination_and_disables_at_boundaries(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_history_page([_history_entry()], total=50, page=1))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/")

    assert response.status_code == 200
    assert "Page 1 of 2" in response.text
    assert response.text.count("disabled") == 1


def test_history_page_htmx_request_returns_only_the_results_fragment(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_history_page([_history_entry()]))

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/history/", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert "<hgroup" not in response.text
    assert "Foo" in response.text
