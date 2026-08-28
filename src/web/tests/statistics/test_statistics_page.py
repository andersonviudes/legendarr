import httpx
from fastapi.testclient import TestClient
from legendarr_web.app import create_app


def _statistics_payload(*, translated_total=0, acquired_total=0, by_provider=None, by_profile=None):
    def _category(total, provider_entries, profile_entries):
        return {
            "total": total,
            "daily": [{"date": "2026-08-27", "count": total}, {"date": "2026-08-28", "count": 0}],
            "by_profile": profile_entries or [],
            "by_provider": provider_entries or [],
        }

    return {
        "translated": _category(translated_total, by_provider, by_profile),
        "acquired": _category(acquired_total, [], []),
    }


def test_statistics_page_shows_counts_and_breakdowns(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_statistics_payload(
                translated_total=3,
                by_provider=[{"label": "deepl", "count": 2}, {"label": "google", "count": 1}],
                by_profile=[{"label": "default", "count": 3}],
            ),
        )

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/statistics/")

    assert response.status_code == 200
    assert "deepl" in response.text
    assert "default" in response.text


def test_statistics_page_shows_empty_state_with_no_activity(stub_backend_client):
    app = create_app()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_statistics_payload())

    stub_backend_client(app, handler=handler)

    with TestClient(app) as client:
        response = client.get("/statistics/")

    assert response.status_code == 200
    assert "No activity recorded yet." in response.text
