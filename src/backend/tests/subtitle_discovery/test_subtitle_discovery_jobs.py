from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_discovery import jobs as jobs_module
from legendarr_backend.subtitle_discovery.jobs import (
    enqueue_full_subtitle_scan,
    enqueue_subtitle_scan,
    register_subtitle_scan_job,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import ScanResult
from sqlmodel import select


def test_register_subtitle_scan_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        subtitle_scan_interval_minutes=45,
        subtitle_scan_max_instances=2,
        subtitle_scan_coalesce=False,
    )

    register_subtitle_scan_job(scheduler, config)

    job = scheduler.get_job("subtitle_discovery_scan_fanout")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 45 * 60


def test_enqueue_subtitle_scan_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_subtitle_scan(
        scheduler, 7, JobQueue.SCAN_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )

    _, kwargs = added[0]
    assert kwargs["id"] == "subtitle_scan:7"
    assert kwargs["executor"] == JobQueue.SCAN_BULK.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_subtitle_scan_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_subtitle_scan(
        scheduler, 7, JobQueue.SCAN_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )
    enqueue_subtitle_scan(
        scheduler, 7, JobQueue.SCAN_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["subtitle_scan:7", "subtitle_scan:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_subtitle_scan_job_persists_discovered_subtitle(
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
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=42,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").write_bytes(b"x" * 42)
    (tmp_path / "Foo" / "Foo.pt-BR.srt").touch()

    scheduler = build_scheduler()
    enqueue_subtitle_scan(
        scheduler,
        media_file.id,
        JobQueue.SCAN_BULK,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )
    job = scheduler.get_job(f"subtitle_scan:{media_file.id}")
    assert job is not None
    job.func()

    rows = list(in_memory_session.exec(select(Subtitle)).all())
    assert len(rows) == 1
    assert rows[0].media_file_id == media_file.id
    assert rows[0].relative_path == "Foo.pt-BR.srt"
    # cascade defaults to False — every existing caller (periodic fan-out, manual
    # full-item scan) keeps this exact behavior.
    assert scheduler.get_job(f"subtitle_acquisition:{media_file.id}") is None


def test_enqueued_subtitle_scan_job_cascades_to_acquisition_when_requested(
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
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=42,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    enqueue_subtitle_scan(
        scheduler,
        media_file.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    job = scheduler.get_job(f"subtitle_scan:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_acquisition:{media_file.id}") is not None


def test_enqueue_subtitle_scan_does_not_downgrade_a_pending_cascade(
    in_memory_session, tmp_path, monkeypatch
):
    """Same race as `media_library`'s equivalent test, one stage down the pipeline: the
    periodic bulk fan-out (cascade=False) must not silently drop a still-pending
    cascade=True subtitle scan for the same file (queued by a scan's own cascade)."""

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
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=42,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    enqueue_subtitle_scan(
        scheduler,
        media_file.id,
        JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    enqueue_subtitle_scan(
        scheduler,
        media_file.id,
        JobQueue.SCAN_BULK,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )

    job = scheduler.get_job(f"subtitle_scan:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_acquisition:{media_file.id}") is not None


def test_enqueued_subtitle_scan_job_forwards_probe_timeout_to_the_scan(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    captured = {}

    def _fake_scan(*_args, **kwargs):
        captured["kwargs"] = kwargs
        return ScanResult(added=0, removed=0)

    monkeypatch.setattr(jobs_module, "scan_subtitles_for_media_file", _fake_scan)
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
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=42,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").write_bytes(b"x" * 42)

    scheduler = build_scheduler()
    enqueue_subtitle_scan(
        scheduler,
        media_file.id,
        JobQueue.SCAN_BULK,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        probe_timeout_seconds=5.0,
    )
    job = scheduler.get_job(f"subtitle_scan:{media_file.id}")
    assert job is not None
    job.func()

    assert captured["kwargs"]["probe_timeout_seconds"] == 5.0


def test_enqueued_subtitle_scan_job_tolerates_deleted_media_file(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_subtitle_scan(
        scheduler, 999, JobQueue.SCAN_BULK, retry_attempts=1, retry_delay_seconds=0.0
    )

    # Must not raise — the row can be gone by the time the job runs.
    job = scheduler.get_job("subtitle_scan:999")
    assert job is not None
    job.func()


def test_enqueue_full_subtitle_scan_enqueues_every_known_media_file(
    in_memory_session, tmp_path, monkeypatch
):
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
    first = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    second = MediaFile(
        movie_id=movie.id, relative_path="Bar.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(first)
    in_memory_session.add(second)
    in_memory_session.commit()

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_full_subtitle_scan(
        scheduler, in_memory_session, retry_attempts=1, retry_delay_seconds=0.0
    )

    assert enqueued == 2
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_scan:{first.id}", f"subtitle_scan:{second.id}"}
    assert all(kwargs["executor"] == JobQueue.SCAN_BULK.value for _, kwargs in added)
