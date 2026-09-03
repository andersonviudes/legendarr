from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_timing_sync import jobs as jobs_module
from legendarr_backend.subtitle_timing_sync.jobs import enqueue_timing_sync


def _arr_service(session, tmp_path):
    return create_arr_service(
        session,
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


def test_enqueue_timing_sync_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_timing_sync(
        scheduler,
        7,
        JobQueue.TIMING_SYNC,
        retry_attempts=2,
        retry_delay_seconds=1.0,
        timeout_seconds=30.0,
    )

    _, kwargs = added[0]
    assert kwargs["id"] == "subtitle_timing_sync:7"
    assert kwargs["executor"] == JobQueue.TIMING_SYNC.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_timing_sync_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_timing_sync(
        scheduler,
        7,
        JobQueue.TIMING_SYNC,
        retry_attempts=2,
        retry_delay_seconds=1.0,
        timeout_seconds=30.0,
    )
    enqueue_timing_sync(
        scheduler,
        7,
        JobQueue.TIMING_SYNC,
        retry_attempts=2,
        retry_delay_seconds=1.0,
        timeout_seconds=30.0,
    )

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["subtitle_timing_sync:7", "subtitle_timing_sync:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_timing_sync_job_tolerates_deleted_subtitle(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_timing_sync(
        scheduler,
        999,
        JobQueue.TIMING_SYNC,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=30.0,
    )

    # Must not raise — the row can be gone by the time the job runs.
    job = scheduler.get_job("subtitle_timing_sync:999")
    assert job is not None
    job.func()


def test_enqueued_timing_sync_job_calls_sync_subtitle_timing_with_resolved_paths(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    calls = []
    monkeypatch.setattr(
        jobs_module,
        "sync_subtitle_timing",
        lambda video_path, subtitle_path, *, timeout_seconds: (
            calls.append((video_path, subtitle_path, timeout_seconds)) or True
        ),
    )

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.en.srt",
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None

    scheduler = build_scheduler()
    enqueue_timing_sync(
        scheduler,
        subtitle.id,
        JobQueue.TIMING_SYNC,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=45.0,
    )
    job = scheduler.get_job(f"subtitle_timing_sync:{subtitle.id}")
    assert job is not None
    job.func()

    assert len(calls) == 1
    video_path, subtitle_path, timeout_seconds = calls[0]
    assert video_path == tmp_path / "Foo" / "Foo.mkv"
    assert subtitle_path == tmp_path / "Foo" / "Foo.en.srt"
    assert timeout_seconds == 45.0


def test_enqueued_timing_sync_job_resolves_reference_subtitle_path(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    calls = []
    monkeypatch.setattr(
        jobs_module,
        "sync_subtitle_timing",
        lambda reference_path, subtitle_path, *, timeout_seconds: (
            calls.append((reference_path, subtitle_path, timeout_seconds)) or True
        ),
    )

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.en.srt",
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    reference_subtitle = Subtitle(
        media_file_id=media_file.id,
        language="fr",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.fr.srt",
        content_hash="test-hash-fr",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.add(reference_subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None
    assert reference_subtitle.id is not None

    scheduler = build_scheduler()
    enqueue_timing_sync(
        scheduler,
        subtitle.id,
        JobQueue.TIMING_SYNC,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=45.0,
        reference_subtitle_id=reference_subtitle.id,
    )
    job = scheduler.get_job(f"subtitle_timing_sync:{subtitle.id}")
    assert job is not None
    job.func()

    assert len(calls) == 1
    reference_path, subtitle_path, timeout_seconds = calls[0]
    assert reference_path == tmp_path / "Foo" / "Foo.fr.srt"
    assert subtitle_path == tmp_path / "Foo" / "Foo.en.srt"
    assert timeout_seconds == 45.0


def test_enqueued_timing_sync_job_skips_when_reference_subtitle_deleted(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    calls = []
    monkeypatch.setattr(
        jobs_module,
        "sync_subtitle_timing",
        lambda reference_path, subtitle_path, *, timeout_seconds: calls.append(
            (reference_path, subtitle_path)
        ),
    )

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language="en",
        origin=SubtitleOrigin.EXTERNAL,
        relative_path="Foo.en.srt",
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(subtitle)
    in_memory_session.commit()
    assert subtitle.id is not None

    scheduler = build_scheduler()
    enqueue_timing_sync(
        scheduler,
        subtitle.id,
        JobQueue.TIMING_SYNC,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        timeout_seconds=45.0,
        reference_subtitle_id=999,
    )
    job = scheduler.get_job(f"subtitle_timing_sync:{subtitle.id}")
    assert job is not None

    # Must not raise — the reference row can be gone by the time the job runs.
    job.func()

    assert calls == []
