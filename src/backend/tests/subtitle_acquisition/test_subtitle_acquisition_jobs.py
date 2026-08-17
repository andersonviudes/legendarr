from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_acquisition import (
    acquire_media_file_subtitle as acquire_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition import jobs as jobs_module
from legendarr_backend.subtitle_acquisition.jobs import (
    enqueue_acquisition,
    enqueue_full_acquisition_scan,
    register_acquisition_job,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_discovery.models import Subtitle
from sqlmodel import select


class _FakeProvider:
    name = "fake"

    def search(
        self,
        title,
        language,
        *,
        imdb_id=None,
        moviehash=None,
        season=None,
        episode=None,
        video_path=None,
        tvdb_id=None,
    ):
        return [SubtitleSearchResult(release_name="Foo", download_id="1", language=language)]

    def download(self, result):
        return "1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"


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


def test_register_acquisition_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        acquisition_interval_minutes=45,
        acquisition_max_instances=2,
        acquisition_coalesce=False,
    )

    register_acquisition_job(scheduler, config)

    job = scheduler.get_job("subtitle_acquisition_fanout")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 45 * 60


def test_enqueue_acquisition_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_acquisition(
        scheduler, 7, JobQueue.ACQUIRE_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )

    _, kwargs = added[0]
    assert kwargs["id"] == "subtitle_acquisition:7"
    assert kwargs["executor"] == JobQueue.ACQUIRE_BULK.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_acquisition_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_acquisition(scheduler, 7, JobQueue.ACQUIRE, retry_attempts=2, retry_delay_seconds=1.0)
    enqueue_acquisition(scheduler, 7, JobQueue.ACQUIRE, retry_attempts=2, retry_delay_seconds=1.0)

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["subtitle_acquisition:7", "subtitle_acquisition:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_acquisition_job_tolerates_deleted_media_file(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_acquisition(scheduler, 999, JobQueue.ACQUIRE, retry_attempts=1, retry_delay_seconds=0.0)

    # Must not raise — the row can be gone by the time the job runs.
    job = scheduler.get_job("subtitle_acquisition:999")
    assert job is not None
    job.func()


def test_enqueued_acquisition_job_downloads_and_persists_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.add(
        LanguageProfile(
            name="default",
            source_languages="en",
            target_languages="pt-BR",
            is_default=True,
        )
    )
    in_memory_session.commit()
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").touch()

    scheduler = build_scheduler()
    enqueue_acquisition(
        scheduler, media_file.id, JobQueue.ACQUIRE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hi" in output.read_text(encoding="utf-8")
    rows = list(in_memory_session.exec(select(Subtitle)).all())
    assert any(row.language == "en" for row in rows)


def test_enqueue_full_acquisition_scan_enqueues_every_known_media_file(
    in_memory_session, tmp_path, monkeypatch
):
    service = _arr_service(in_memory_session, tmp_path)
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

    enqueued = enqueue_full_acquisition_scan(
        scheduler, in_memory_session, retry_attempts=1, retry_delay_seconds=0.0
    )

    assert enqueued == 2
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_acquisition:{first.id}", f"subtitle_acquisition:{second.id}"}
    assert all(kwargs["executor"] == JobQueue.ACQUIRE_BULK.value for _, kwargs in added)
