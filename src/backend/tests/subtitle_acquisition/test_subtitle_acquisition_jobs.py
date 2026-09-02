from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_acquisition import (
    acquire_media_file_subtitle as acquire_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition import jobs as jobs_module
from legendarr_backend.subtitle_acquisition import (
    upgrade_media_file_subtitle as upgrade_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition.acquire_media_file_subtitle import AcquisitionResult
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    CandidateEvaluation,
)
from legendarr_backend.subtitle_acquisition.jobs import (
    enqueue_acquisition,
    enqueue_full_acquisition_scan,
    enqueue_item_acquisition_scan,
    register_acquisition_job,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_discovery.models import Subtitle, SubtitleScanState
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
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
        series_imdb_id=None,
    ):
        return [SubtitleSearchResult(release_name="Foo", download_id="1", language=language)]

    def download(self, result):
        return "1\n00:00:00,000 --> 00:00:15,000\nHi\n\n"


class _NoMatchProvider:
    name = "no_match"

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
        series_imdb_id=None,
    ):
        return []

    def download(self, result):
        raise AssertionError("never called — search returns no candidates")


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
    # cascade defaults to False — every existing caller (periodic fan-out, manual
    # full-item scan) keeps this exact behavior.
    assert scheduler.get_job(f"subtitle_translation:{media_file.id}") is None


def test_enqueue_acquisition_passes_speech_to_text_settings_through(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    captured = {}

    def _fake_acquire(session, media_file, video_path, **kwargs):
        captured.update(kwargs)
        return AcquisitionResult(skipped_reason="no_provider_configured")

    monkeypatch.setattr(jobs_module, "acquire_subtitle_for_media_file", _fake_acquire)

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
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
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        speech_to_text_model_size="small",
        speech_to_text_timeout_seconds=900.0,
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert captured["speech_to_text_model_size"] == "small"
    assert captured["speech_to_text_timeout_seconds"] == 900.0
    assert captured["speech_to_text_model_dir"] is not None


def test_enqueued_acquisition_job_wires_on_progress_into_report_progress(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    captured = {}

    def _fake_acquire(session, media_file, video_path, **kwargs):
        captured.update(kwargs)
        return AcquisitionResult(skipped_reason="no_provider_configured")

    monkeypatch.setattr(jobs_module, "acquire_subtitle_for_media_file", _fake_acquire)
    progress_calls = []
    monkeypatch.setattr(
        jobs_module,
        "report_progress",
        lambda job_id, **kwargs: progress_calls.append((job_id, kwargs)),
    )

    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
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

    captured["on_progress"](1, 2, "en", "opensubtitles")

    assert progress_calls == [
        (
            f"subtitle_acquisition:{media_file.id}",
            {
                "phase": "searching",
                "current": 1,
                "total": 2,
                "language": "en",
                "provider": "opensubtitles",
            },
        )
    ]


def test_enqueued_acquisition_job_cascades_to_translation_when_requested(
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
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_translation:{media_file.id}") is not None


def test_enqueued_acquisition_job_does_not_cascade_when_auto_translate_disabled(
    in_memory_session, tmp_path, monkeypatch
):
    """A profile with `auto_translate` off must not have translation silently
    re-enabled through the acquisition cascade — same gate as the periodic translation
    fan-out's own `needs_translation` check."""

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
            auto_translate=False,
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
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_translation:{media_file.id}") is None


def test_enqueued_acquisition_job_does_not_cascade_on_no_match(
    in_memory_session, tmp_path, monkeypatch
):
    """ROADMAP 0.12.0 loop guard: an unconditional cascade here would oscillate forever
    against `subtitle_translation.jobs.run_translation`'s own cascade back into
    acquisition on a missing source subtitle, so a failed acquisition (nothing found)
    must not enqueue a follow-up translation job."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_NoMatchProvider()],
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
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_translation:{media_file.id}") is None


def test_enqueued_acquisition_job_upgrades_an_existing_source_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    """When acquisition is a pure no-op (a source-language subtitle already exists),
    the job falls through to `upgrade_subtitle_for_media_file` — ROADMAP 0.12.0's
    upgrade/replace pass, checked here at the job level since `acquire_media_file_subtitle`
    and `upgrade_media_file_subtitle` each have their own dedicated unit tests."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        upgrade_media_file_subtitle_module,
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text("old", encoding="utf-8")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo.en.srt",
            content_hash="old-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="old-provider",
        release_name="Foo.OLD",
        download_id="old-1",
        evaluation=CandidateEvaluation(score=0.1, title_similarity=0.1, attribute_matches={}),
    )
    in_memory_session.commit()

    scheduler = build_scheduler()
    enqueue_acquisition(
        scheduler, media_file.id, JobQueue.ACQUIRE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hi" in output.read_text(encoding="utf-8")


def test_enqueue_acquisition_does_not_downgrade_a_pending_cascade(
    in_memory_session, tmp_path, monkeypatch
):
    """Same race as `subtitle_discovery`'s equivalent test, one stage further down the
    pipeline."""

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
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )
    enqueue_acquisition(
        scheduler,
        media_file.id,
        JobQueue.ACQUIRE_BULK,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )

    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_translation:{media_file.id}") is not None


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
    assert first.id is not None
    assert second.id is not None
    now = datetime.now(UTC)
    in_memory_session.add(
        SubtitleScanState(media_file_id=first.id, probed_at=now, probed_size_bytes=1)
    )
    in_memory_session.add(
        SubtitleScanState(media_file_id=second.id, probed_at=now, probed_size_bytes=1)
    )
    in_memory_session.commit()

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_full_acquisition_scan(
        scheduler,
        in_memory_session,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        upgrade_recheck_after=timedelta(hours=24),
    )

    assert enqueued == 2
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_acquisition:{first.id}", f"subtitle_acquisition:{second.id}"}
    assert all(kwargs["executor"] == JobQueue.ACQUIRE_BULK.value for _, kwargs in added)


def test_enqueue_full_acquisition_scan_skips_media_file_without_subtitle_scan(
    in_memory_session, tmp_path, monkeypatch
):
    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    in_memory_session.add(movie)
    in_memory_session.commit()
    scanned = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    not_yet_scanned = MediaFile(
        movie_id=movie.id, relative_path="Bar.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(scanned)
    in_memory_session.add(not_yet_scanned)
    in_memory_session.commit()
    assert scanned.id is not None
    in_memory_session.add(
        SubtitleScanState(
            media_file_id=scanned.id, probed_at=datetime.now(UTC), probed_size_bytes=1
        )
    )
    in_memory_session.commit()
    # `not_yet_scanned` has no `SubtitleScanState` row — discovery hasn't run for it yet.

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_full_acquisition_scan(
        scheduler,
        in_memory_session,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        upgrade_recheck_after=timedelta(hours=24),
    )

    assert enqueued == 1
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_acquisition:{scanned.id}"}


def test_enqueue_item_acquisition_scan_enqueues_only_that_movies_media_files(
    in_memory_session, tmp_path, monkeypatch
):
    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    target = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    other = Movie(arr_service_id=service.id, arr_id=2, title="Bar", remote_path="/remote/Bar")
    in_memory_session.add(target)
    in_memory_session.add(other)
    in_memory_session.commit()
    wanted = MediaFile(
        movie_id=target.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    unrelated = MediaFile(
        movie_id=other.id, relative_path="Bar.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(wanted)
    in_memory_session.add(unrelated)
    in_memory_session.commit()
    assert target.id is not None

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_item_acquisition_scan(
        scheduler,
        in_memory_session,
        "movie",
        target.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )

    assert enqueued == 1
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_acquisition:{wanted.id}"}
    assert all(kwargs["executor"] == JobQueue.ACQUIRE.value for _, kwargs in added)


def test_enqueue_item_acquisition_scan_enqueues_only_that_series_media_files(
    in_memory_session, tmp_path, monkeypatch
):
    service = _arr_service(in_memory_session, tmp_path)
    assert service.id is not None
    target = Series(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    other = Series(arr_service_id=service.id, arr_id=2, title="Bar", remote_path="/remote/Bar")
    in_memory_session.add(target)
    in_memory_session.add(other)
    in_memory_session.commit()
    wanted = MediaFile(
        series_id=target.id,
        relative_path="Foo.S01E01.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    unrelated = MediaFile(
        series_id=other.id,
        relative_path="Bar.S01E01.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(wanted)
    in_memory_session.add(unrelated)
    in_memory_session.commit()
    assert target.id is not None

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_item_acquisition_scan(
        scheduler,
        in_memory_session,
        "series",
        target.id,
        JobQueue.ACQUIRE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
    )

    assert enqueued == 1
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_acquisition:{wanted.id}"}


def test_enqueued_acquisition_job_notifies_media_servers_after_download(
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
    notified = []
    monkeypatch.setattr(
        jobs_module,
        "notify_media_servers_of_subtitle_write",
        lambda session, video_path: notified.append(video_path),
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

    assert notified == [tmp_path / "Foo" / "Foo.mkv"]


def test_enqueued_acquisition_job_does_not_notify_media_servers_on_no_match(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_NoMatchProvider()],
    )
    notified = []
    monkeypatch.setattr(
        jobs_module,
        "notify_media_servers_of_subtitle_write",
        lambda session, video_path: notified.append(video_path),
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

    assert notified == []


def test_enqueued_acquisition_job_notifies_media_servers_after_upgrade(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        upgrade_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )
    notified = []
    monkeypatch.setattr(
        jobs_module,
        "notify_media_servers_of_subtitle_write",
        lambda session, video_path: notified.append(video_path),
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text("old", encoding="utf-8")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo.en.srt",
            content_hash="old-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    record_acquired_subtitle(
        in_memory_session,
        media_file.id,
        "en",
        provider="old-provider",
        release_name="Foo.OLD",
        download_id="old-1",
        evaluation=CandidateEvaluation(score=0.1, title_similarity=0.1, attribute_matches={}),
    )
    in_memory_session.commit()

    scheduler = build_scheduler()
    enqueue_acquisition(
        scheduler, media_file.id, JobQueue.ACQUIRE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert job is not None
    job.func()

    assert notified == [tmp_path / "Foo" / "Foo.mkv"]
