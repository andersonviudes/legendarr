import pytest
from legendarr_backend.arr_clients.base import MediaItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library import sync_media_library as sync_module
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_library.sync_media_library import sync_media_library
from sqlmodel import select


class _FakeClient:
    def __init__(self, items: list[MediaItem]):
        self._items = items

    def list_items(self) -> list[MediaItem]:
        return self._items

    def close(self) -> None:
        pass


class _FailingClient:
    def list_items(self) -> list[MediaItem]:
        raise ConnectionError("server unreachable")

    def close(self) -> None:
        pass


@pytest.fixture
def fake_clients(monkeypatch) -> dict:
    """Clients handed out by the patched `build_client`, keyed by ArrService id."""
    clients: dict = {}
    monkeypatch.setattr(sync_module, "build_client", lambda arr_service: clients[arr_service.id])
    return clients


def _service_input(name: str, service_type: str, **overrides) -> ArrServiceInput:
    data = {
        "name": name,
        "service_type": service_type,
        "host": name,
        "port": 7878,
        "api_key": "api-key",
    }
    data.update(overrides)
    return ArrServiceInput(**data)


def _movies(session) -> list[Movie]:
    return list(session.exec(select(Movie)).all())


def _series(session) -> list[Series]:
    return list(session.exec(select(Series)).all())


def test_sync_with_no_connections_returns_zero_counts(in_memory_session):
    result = sync_media_library(in_memory_session)

    assert result.movies_synced == 0
    assert result.series_synced == 0


def test_sync_persists_movies_with_remote_path_untouched(in_memory_session, fake_clients):
    radarr = create_arr_service(
        in_memory_session,
        _service_input(
            "radarr",
            "radarr",
            remote_path_prefix="/movies",
            local_path_prefix="/media/movies",
        ),
    )
    fake_clients[radarr.id] = _FakeClient([MediaItem(id=1, title="Foo", path="/movies/Foo")])

    result = sync_media_library(in_memory_session)

    assert result.movies_synced == 1
    assert result.series_synced == 0
    movie = _movies(in_memory_session)[0]
    assert movie.arr_service_id == radarr.id
    assert movie.arr_id == 1
    assert movie.title == "Foo"
    assert movie.remote_path == "/movies/Foo"


def test_sync_persists_series(in_memory_session, fake_clients):
    sonarr = create_arr_service(in_memory_session, _service_input("sonarr", "sonarr"))
    fake_clients[sonarr.id] = _FakeClient([MediaItem(id=7, title="Bar", path="/tv/Bar")])

    result = sync_media_library(in_memory_session)

    assert result.series_synced == 1
    series = _series(in_memory_session)[0]
    assert series.arr_service_id == sonarr.id
    assert series.remote_path == "/tv/Bar"


def test_sync_upserts_changed_items_without_duplicating(in_memory_session, fake_clients):
    radarr = create_arr_service(in_memory_session, _service_input("radarr", "radarr"))
    fake_clients[radarr.id] = _FakeClient([MediaItem(id=1, title="Foo", path="/movies/Foo")])
    sync_media_library(in_memory_session)

    fake_clients[radarr.id] = _FakeClient([MediaItem(id=1, title="Foo HD", path="/movies2/Foo")])
    sync_media_library(in_memory_session)

    movies = _movies(in_memory_session)
    assert len(movies) == 1
    assert movies[0].title == "Foo HD"
    assert movies[0].remote_path == "/movies2/Foo"


def test_sync_deletes_stale_rows_scoped_to_their_connection(in_memory_session, fake_clients):
    radarr_a = create_arr_service(in_memory_session, _service_input("radarr-a", "radarr"))
    radarr_b = create_arr_service(in_memory_session, _service_input("radarr-b", "radarr"))
    fake_clients[radarr_a.id] = _FakeClient([MediaItem(id=1, title="A", path="/movies/A")])
    fake_clients[radarr_b.id] = _FakeClient([MediaItem(id=1, title="B", path="/filmes/B")])
    sync_media_library(in_memory_session)

    fake_clients[radarr_a.id] = _FakeClient([])
    sync_media_library(in_memory_session)

    movies = _movies(in_memory_session)
    assert len(movies) == 1
    assert movies[0].arr_service_id == radarr_b.id
    assert movies[0].title == "B"


def test_sync_skips_disabled_connections(in_memory_session, fake_clients):
    radarr = create_arr_service(
        in_memory_session, _service_input("radarr", "radarr", enabled=False)
    )
    fake_clients[radarr.id] = _FakeClient([MediaItem(id=1, title="Foo", path="/movies/Foo")])

    result = sync_media_library(in_memory_session)

    assert result.movies_synced == 0
    assert _movies(in_memory_session) == []


def test_failing_connection_does_not_block_others(in_memory_session, fake_clients):
    broken = create_arr_service(in_memory_session, _service_input("broken", "radarr"))
    healthy = create_arr_service(in_memory_session, _service_input("healthy", "sonarr"))
    in_memory_session.add(
        Movie(arr_service_id=broken.id, arr_id=9, title="Old", remote_path="/movies/Old")
    )
    in_memory_session.commit()
    fake_clients[broken.id] = _FailingClient()
    fake_clients[healthy.id] = _FakeClient([MediaItem(id=2, title="Bar", path="/tv/Bar")])

    result = sync_media_library(in_memory_session)

    assert result.movies_synced == 0
    assert result.series_synced == 1
    kept = _movies(in_memory_session)
    assert len(kept) == 1
    assert kept[0].title == "Old"
    assert len(_series(in_memory_session)) == 1
