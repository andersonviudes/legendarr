from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_metadata import fetch_metadata
from legendarr_backend.media_metadata import jobs as jobs_module
from legendarr_backend.media_metadata.jobs import (
    enqueue_media_metadata_fetch,
    enqueue_metadata_refetch,
    register_metadata_refresh_job,
    register_poster_cache_cleanup_job,
)
from legendarr_backend.media_metadata.manage_metadata_provider import (
    ensure_metadata_providers_seeded,
    list_metadata_providers,
    update_metadata_provider,
)
from legendarr_backend.media_metadata.models import MediaMetadata
from legendarr_backend.media_metadata.providers.base import MetadataResult
from legendarr_backend.media_metadata.schemas import MetadataProviderConfigInput
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from sqlmodel import select


class _StubProvider:
    def __init__(self, result: MetadataResult | None) -> None:
        self._result = result

    def fetch(self, **kwargs) -> MetadataResult | None:
        return self._result

    def close(self) -> None:
        pass


def _seed_movie(session) -> Movie:
    arr_service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    assert arr_service.id is not None
    movie = Movie(
        arr_service_id=arr_service.id, arr_id=1, title="A Movie", remote_path="/p", imdb_id="tt1"
    )
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def _seed_series(session) -> Series:
    arr_service = ArrService(name="sonarr", service_type="sonarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    assert arr_service.id is not None
    series = Series(
        arr_service_id=arr_service.id, arr_id=1, title="A Series", remote_path="/p", tvdb_id=1
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    return series


def _configure_all_providers(session) -> None:
    ensure_metadata_providers_seeded(session)
    for provider in list_metadata_providers(session):
        assert provider.id is not None
        update_metadata_provider(session, provider.id, MetadataProviderConfigInput(api_key="key"))


def test_enqueue_media_metadata_fetch_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_metadata_fetch(scheduler, "movie", 7, retry_attempts=2, retry_delay_seconds=1.0)

    _, kwargs = added[0]
    assert kwargs["id"] == "media_metadata_fetch:movie:7"
    assert kwargs["executor"] == JobQueue.METADATA_BULK.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_media_metadata_fetch_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_metadata_fetch(scheduler, "movie", 7, retry_attempts=2, retry_delay_seconds=1.0)
    enqueue_media_metadata_fetch(scheduler, "movie", 7, retry_attempts=2, retry_delay_seconds=1.0)

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["media_metadata_fetch:movie:7", "media_metadata_fetch:movie:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueue_metadata_refetch_enqueues_every_movie_and_series(in_memory_session, monkeypatch):
    session = in_memory_session
    movie = _seed_movie(session)
    series = _seed_series(session)
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    movies_enqueued, series_enqueued = enqueue_metadata_refetch(
        scheduler, session, retry_attempts=2, retry_delay_seconds=1.0
    )

    assert movies_enqueued == 1
    assert series_enqueued == 1
    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == [
        f"media_metadata_fetch:movie:{movie.id}",
        f"media_metadata_fetch:series:{series.id}",
    ]


def test_enqueued_metadata_fetch_job_fetches_and_stores_metadata(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    session = in_memory_session
    _configure_all_providers(session)
    movie = _seed_movie(session)
    assert movie.id is not None
    monkeypatch.setattr(
        fetch_metadata,
        "build_metadata_provider",
        lambda config: _StubProvider(MetadataResult(overview="fetched", year=2024)),
    )

    scheduler = build_scheduler()
    enqueue_media_metadata_fetch(
        scheduler, "movie", movie.id, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"media_metadata_fetch:movie:{movie.id}")
    assert job is not None
    job.func()

    stored = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie.id)).one()
    assert stored.overview == "fetched"
    assert stored.year == 2024


def test_enqueued_metadata_fetch_job_overwrites_existing_metadata_row(
    in_memory_session, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    session = in_memory_session
    _configure_all_providers(session)
    movie = _seed_movie(session)
    assert movie.id is not None
    session.add(
        MediaMetadata(
            movie_id=movie.id, overview="stale overview", year=1990, fetched_at=datetime.now(UTC)
        )
    )
    session.commit()

    monkeypatch.setattr(
        fetch_metadata,
        "build_metadata_provider",
        lambda config: _StubProvider(MetadataResult(overview="fresh overview", year=2024)),
    )

    scheduler = build_scheduler()
    enqueue_media_metadata_fetch(
        scheduler, "movie", movie.id, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"media_metadata_fetch:movie:{movie.id}")
    assert job is not None
    job.func()

    rows = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie.id)).all()
    assert len(rows) == 1
    assert rows[0].overview == "fresh overview"
    assert rows[0].year == 2024


def test_enqueued_metadata_fetch_job_tolerates_deleted_item(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_media_metadata_fetch(scheduler, "movie", 999, retry_attempts=1, retry_delay_seconds=0.0)
    job = scheduler.get_job("media_metadata_fetch:movie:999")
    assert job is not None


def test_register_metadata_refresh_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        metadata_refresh_interval_minutes=30,
        metadata_refresh_retry_attempts=5,
        metadata_refresh_retry_delay_seconds=2.0,
        metadata_refresh_max_instances=3,
        metadata_refresh_coalesce=False,
    )

    register_metadata_refresh_job(scheduler, config)

    job = scheduler.get_job("media_metadata_refresh_fanout")
    assert job is not None
    assert job.executor == JobQueue.METADATA_BULK.value
    assert job.max_instances == 3
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 30 * 60


def test_register_poster_cache_cleanup_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        poster_cache_cleanup_interval_minutes=60,
        poster_cache_cleanup_max_instances=2,
        poster_cache_cleanup_coalesce=False,
    )

    register_poster_cache_cleanup_job(scheduler, config)

    job = scheduler.get_job("media_metadata_poster_cache_cleanup")
    assert job is not None
    assert job.executor == JobQueue.METADATA_BULK.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 60 * 60


def test_metadata_refresh_job_fanout_calls_enqueue_metadata_refetch(monkeypatch):
    """The registered job's body reuses `enqueue_metadata_refetch` verbatim — this
    confirms the wiring without re-testing that function's own fan-out behavior, already
    covered by `test_enqueue_metadata_refetch_enqueues_every_movie_and_series`."""
    calls: list[dict] = []
    monkeypatch.setattr(
        jobs_module,
        "enqueue_metadata_refetch",
        lambda scheduler, session, **kwargs: calls.append(kwargs) or (0, 0),
    )

    @contextmanager
    def _session():
        yield None

    monkeypatch.setattr(jobs_module, "get_session", _session)
    scheduler = build_scheduler()
    config = AppConfigFile(
        metadata_refresh_interval_minutes=1,
        metadata_refresh_retry_attempts=7,
        metadata_refresh_retry_delay_seconds=1.5,
    )

    register_metadata_refresh_job(scheduler, config)
    job = scheduler.get_job("media_metadata_refresh_fanout")
    assert job is not None
    job.func()

    assert calls == [{"retry_attempts": 7, "retry_delay_seconds": 1.5}]


def test_poster_cache_cleanup_job_sweep_calls_cleanup_orphaned_posters(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(
        jobs_module, "cleanup_orphaned_posters", lambda session: calls.append(session) or 3
    )

    @contextmanager
    def _session():
        yield "the-session"

    monkeypatch.setattr(jobs_module, "get_session", _session)
    scheduler = build_scheduler()
    config = AppConfigFile(poster_cache_cleanup_interval_minutes=1)

    register_poster_cache_cleanup_job(scheduler, config)
    job = scheduler.get_job("media_metadata_poster_cache_cleanup")
    assert job is not None
    job.func()

    assert calls == ["the-session"]

    job.func()  # must not raise
