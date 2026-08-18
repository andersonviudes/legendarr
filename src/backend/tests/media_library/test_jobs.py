from contextlib import contextmanager
from functools import partial

from legendarr_backend.arr_clients.base import MediaItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.media_library import jobs as jobs_module
from legendarr_backend.media_library import sync_media_library as sync_module
from legendarr_backend.media_library.jobs import (
    enqueue_media_scan,
    enqueue_media_sync,
    register_history_poll_job,
    register_scan_job,
    register_sync_job,
)
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_discovery.jobs import enqueue_subtitle_scan
from sqlmodel import select


class _FakeClient:
    def __init__(self, items: list[MediaItem]):
        self._items = items

    def list_items(self) -> list[MediaItem]:
        return self._items

    def close(self) -> None:
        pass


def test_register_sync_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        sync_interval_minutes=30,
        sync_retry_attempts=5,
        sync_retry_delay_seconds=2.0,
        sync_max_instances=3,
        sync_coalesce=False,
    )

    register_sync_job(scheduler, config)

    job = scheduler.get_job("media_library_sync")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 3
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 30 * 60


def test_register_scan_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        scan_interval_minutes=45,
        scan_max_instances=2,
        scan_coalesce=False,
    )

    register_scan_job(scheduler, config)

    job = scheduler.get_job("media_library_scan_fanout")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 45 * 60


def test_register_history_poll_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(history_poll_interval_minutes=10)

    register_history_poll_job(scheduler, config)

    job = scheduler.get_job("arr_history_poll")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.trigger.interval.total_seconds() == 10 * 60


def test_enqueue_media_sync_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_sync(scheduler, retry_attempts=2, retry_delay_seconds=1.0)

    _, kwargs = added[0]
    assert kwargs["id"] == "media_library_sync_manual"
    assert kwargs["executor"] == JobQueue.SYNC.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_media_sync_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_sync(scheduler, retry_attempts=2, retry_delay_seconds=1.0)
    enqueue_media_sync(scheduler, retry_attempts=2, retry_delay_seconds=1.0)

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["media_library_sync_manual", "media_library_sync_manual"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_sync_job_syncs_the_library(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        sync_module,
        "build_client",
        lambda arr_service: _FakeClient([MediaItem(id=1, title="Foo", path="/tv/Foo")]),
    )
    create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="sonarr", service_type="sonarr", host="sonarr", port=8989, api_key="k"
        ),
    )

    scheduler = build_scheduler()
    enqueue_media_sync(scheduler, retry_attempts=1, retry_delay_seconds=0.0)
    job = scheduler.get_job("media_library_sync_manual")
    assert job is not None
    job.func()

    series = list(in_memory_session.exec(select(Series)).all())
    assert len(series) == 1
    assert series[0].title == "Foo"


def test_enqueue_media_scan_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_scan(
        scheduler, "movie", 7, JobQueue.SCAN, retry_attempts=2, retry_delay_seconds=1.0
    )

    _, kwargs = added[0]
    assert kwargs["id"] == "media_scan:movie:7"
    assert kwargs["executor"] == JobQueue.SCAN.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_media_scan_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_media_scan(
        scheduler, "movie", 7, JobQueue.SCAN, retry_attempts=2, retry_delay_seconds=1.0
    )
    enqueue_media_scan(
        scheduler, "movie", 7, JobQueue.SCAN_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["media_scan:movie:7", "media_scan:movie:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_scan_job_scans_the_item(in_memory_session, tmp_path, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    assert movie.id is not None
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    enqueue_media_scan(
        scheduler,
        "movie",
        movie.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )
    job = scheduler.get_job("media_scan:movie:1")
    assert job is not None
    job.func()

    rows = list(in_memory_session.exec(select(MediaFile)).all())
    assert len(rows) == 1
    assert rows[0].relative_path == "Foo.mkv"
    assert rows[0].size_bytes == 42
    # cascade defaults to False — every existing caller (periodic fan-out, history
    # poll, full-library manual scan) keeps this exact behavior.
    assert scheduler.get_job(f"subtitle_scan:{rows[0].id}") is None


def test_enqueued_scan_job_cascades_to_subtitle_scan_when_requested(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    assert movie.id is not None
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    on_cascade = partial(
        enqueue_subtitle_scan,
        scheduler,
        queue=JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    enqueue_media_scan(
        scheduler,
        "movie",
        movie.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
        on_cascade=on_cascade,
    )
    job = scheduler.get_job("media_scan:movie:1")
    assert job is not None
    job.func()

    # A file the scan itself just discovered is included too — not just files that
    # already existed before the scan ran.
    rows = list(in_memory_session.exec(select(MediaFile)).all())
    assert len(rows) == 1
    assert scheduler.get_job(f"subtitle_scan:{rows[0].id}") is not None


def test_enqueue_media_scan_does_not_downgrade_a_pending_cascade(
    in_memory_session, tmp_path, monkeypatch
):
    """A history poll or periodic fan-out re-enqueue (cascade=False) racing an Arr
    webhook's still-pending cascade=True job for the same item must not silently drop
    the cascade — the job id doesn't encode `cascade`, so `replace_existing` would
    otherwise let the second, non-cascading enqueue win outright."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    service = create_arr_service(
        in_memory_session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    assert movie.id is not None
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    on_cascade = partial(
        enqueue_subtitle_scan,
        scheduler,
        queue=JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    # Arr webhook: cascade=True.
    enqueue_media_scan(
        scheduler,
        "movie",
        movie.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
        on_cascade=on_cascade,
    )
    # History poll races the same item before the first job runs: cascade=False.
    enqueue_media_scan(
        scheduler,
        "movie",
        movie.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        on_cascade=on_cascade,
    )

    job = scheduler.get_job("media_scan:movie:1")
    assert job is not None
    job.func()

    rows = list(in_memory_session.exec(select(MediaFile)).all())
    assert len(rows) == 1
    assert scheduler.get_job(f"subtitle_scan:{rows[0].id}") is not None


def test_enqueued_scan_job_tolerates_deleted_item(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_media_scan(
        scheduler, "movie", 999, JobQueue.SCAN, retry_attempts=1, retry_delay_seconds=0.0
    )

    # Must not raise — the row can be gone by the time the job runs.
    job = scheduler.get_job("media_scan:movie:999")
    assert job is not None
    job.func()
