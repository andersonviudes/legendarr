from datetime import UTC, datetime, timedelta

import pytest
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.models import ArrServiceType
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library import poll_arr_history as poll_module
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_library.poll_arr_history import poll_arr_history


class _FakeClient:
    def __init__(self, imported_ids: list[int]):
        self._imported_ids = imported_ids
        self.since: datetime | None = None

    def list_recent_import_ids(self, since: datetime) -> list[int]:
        self.since = since
        return self._imported_ids

    def close(self) -> None:
        pass


class _FailingClient:
    def list_recent_import_ids(self, since: datetime) -> list[int]:
        raise ConnectionError("server unreachable")

    def close(self) -> None:
        pass


@pytest.fixture
def fake_clients(monkeypatch) -> dict[int, object]:
    """Clients handed out by the patched `build_client`, keyed by ArrService id."""
    clients: dict[int, object] = {}
    monkeypatch.setattr(poll_module, "build_client", lambda arr_service: clients[arr_service.id])
    return clients


@pytest.fixture
def enqueued() -> list[tuple[str, int]]:
    return []


def _record(calls: list[tuple[str, int]]):
    """Adapt the two-argument EnqueueScan call to a single list of tuples."""
    return lambda kind, media_id: calls.append((kind, media_id))


def _create_service(session, name: str, service_type: ArrServiceType, enabled: bool = True):
    return create_arr_service(
        session,
        ArrServiceInput(
            name=name,
            service_type=service_type,
            host=name,
            port=7878,
            api_key="api-key",
            enabled=enabled,
        ),
    )


def _movie(session, arr_service, arr_id: int) -> Movie:
    movie = Movie(
        arr_service_id=arr_service.id, arr_id=arr_id, title=f"M{arr_id}", remote_path="/m"
    )
    session.add(movie)
    session.commit()
    return movie


def test_poll_enqueues_scans_for_imported_items(in_memory_session, fake_clients, enqueued):
    radarr = _create_service(in_memory_session, "radarr", "radarr")
    movie = _movie(in_memory_session, radarr, arr_id=42)
    fake_clients[radarr.id] = _FakeClient([42])

    result = poll_arr_history(
        in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15
    )

    assert result.scans_enqueued == 1
    assert enqueued == [("movie", movie.id)]


def test_poll_skips_imported_ids_the_sync_has_not_persisted(
    in_memory_session, fake_clients, enqueued
):
    radarr = _create_service(in_memory_session, "radarr", "radarr")
    fake_clients[radarr.id] = _FakeClient([999])

    result = poll_arr_history(
        in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15
    )

    assert result.scans_enqueued == 0
    assert enqueued == []


def test_poll_maps_series_kind_for_sonarr(in_memory_session, fake_clients, enqueued):
    sonarr = _create_service(in_memory_session, "sonarr", "sonarr")
    assert sonarr.id is not None
    series = Series(arr_service_id=sonarr.id, arr_id=7, title="S", remote_path="/s")
    in_memory_session.add(series)
    in_memory_session.commit()
    fake_clients[sonarr.id] = _FakeClient([7])

    poll_arr_history(in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15)

    assert enqueued == [("series", series.id)]


def test_poll_since_window_covers_two_intervals(in_memory_session, fake_clients, enqueued):
    radarr = _create_service(in_memory_session, "radarr", "radarr")
    client = _FakeClient([])
    fake_clients[radarr.id] = client

    before = datetime.now(UTC)
    poll_arr_history(in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15)
    after = datetime.now(UTC)

    assert client.since is not None
    assert before - timedelta(minutes=30) <= client.since <= after - timedelta(minutes=30)


def test_failing_connection_does_not_block_others(in_memory_session, fake_clients, enqueued):
    broken = _create_service(in_memory_session, "broken", "radarr")
    healthy = _create_service(in_memory_session, "healthy", "sonarr")
    assert healthy.id is not None
    series = Series(arr_service_id=healthy.id, arr_id=7, title="S", remote_path="/s")
    in_memory_session.add(series)
    in_memory_session.commit()
    fake_clients[broken.id] = _FailingClient()
    fake_clients[healthy.id] = _FakeClient([7])

    result = poll_arr_history(
        in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15
    )

    assert result.scans_enqueued == 1
    assert enqueued == [("series", series.id)]


def test_poll_skips_disabled_connections(in_memory_session, fake_clients, enqueued):
    radarr = _create_service(in_memory_session, "radarr", "radarr", enabled=False)
    _movie(in_memory_session, radarr, arr_id=42)
    fake_clients[radarr.id] = _FakeClient([42])

    result = poll_arr_history(
        in_memory_session, enqueue_scan=_record(enqueued), poll_interval_minutes=15
    )

    assert result.scans_enqueued == 0
