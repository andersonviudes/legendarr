from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.http_client.client import ProviderHttpClient
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_translation import jobs as jobs_module
from legendarr_backend.subtitle_translation.jobs import (
    enqueue_full_translation_scan,
    enqueue_translation,
    register_translation_job,
)
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from sqlmodel import select


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


def test_register_translation_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        translate_interval_minutes=45,
        translate_max_instances=2,
        translate_coalesce=False,
    )

    register_translation_job(scheduler, config)

    job = scheduler.get_job("subtitle_translation_fanout")
    assert job is not None
    assert job.executor == JobQueue.SYNC.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 45 * 60


def test_enqueue_translation_adds_adhoc_job_with_event_safe_policy(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_translation(
        scheduler, 7, JobQueue.TRANSLATE_BULK, retry_attempts=2, retry_delay_seconds=1.0
    )

    _, kwargs = added[0]
    assert kwargs["id"] == "subtitle_translation:7"
    assert kwargs["executor"] == JobQueue.TRANSLATE_BULK.value
    assert kwargs["misfire_grace_time"] is None


def test_enqueue_translation_dedupes_by_stable_job_id(monkeypatch):
    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueue_translation(scheduler, 7, JobQueue.TRANSLATE, retry_attempts=2, retry_delay_seconds=1.0)
    enqueue_translation(scheduler, 7, JobQueue.TRANSLATE, retry_attempts=2, retry_delay_seconds=1.0)

    ids = [kwargs["id"] for _, kwargs in added]
    assert ids == ["subtitle_translation:7", "subtitle_translation:7"]
    assert all(kwargs["replace_existing"] for _, kwargs in added)


def test_enqueued_translation_job_tolerates_deleted_media_file(in_memory_session, monkeypatch):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

    scheduler = build_scheduler()
    enqueue_translation(
        scheduler, 999, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )

    # Must not raise — the row can be gone by the time the job runs.
    job = scheduler.get_job("subtitle_translation:999")
    assert job is not None
    job.func()


def test_enqueued_translation_job_falls_back_to_acquisition_on_no_source_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    """ROADMAP 0.12.0: a translation run that finds no source-language subtitle yet
    cascades into an acquisition run instead of just no-op'ing, closing the gap where
    only the webhook/import path had this ordering."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

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
    enqueue_translation(
        scheduler, media_file.id, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    acquisition_job = scheduler.get_job(f"subtitle_acquisition:{media_file.id}")
    assert acquisition_job is not None
    assert getattr(acquisition_job.func, "cascade", False) is True


def test_enqueued_translation_job_does_not_fall_back_on_missing_manual_source(
    in_memory_session, tmp_path, monkeypatch
):
    """A manually-picked `source_subtitle_id` that no longer exists is
    `skipped_reason="source_subtitle_not_found"`, not `"no_source_subtitle"` — an explicit
    user override acquisition can't resolve, so it must not trigger the fallback."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)

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
    enqueue_translation(
        scheduler,
        media_file.id,
        JobQueue.TRANSLATE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        source_subtitle_id=999999,
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    assert scheduler.get_job(f"subtitle_acquisition:{media_file.id}") is None


def test_enqueued_translation_job_writes_translated_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {"translations": [{"text": "olá"}]},
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

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
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, tmp_path / "Foo" / "Foo.mkv")
    in_memory_session.commit()

    scheduler = build_scheduler()
    enqueue_translation(
        scheduler, media_file.id, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "olá" in output.read_text(encoding="utf-8")
    rows = list(in_memory_session.exec(select(Subtitle)).all())
    assert any(row.language == "pt-br" for row in rows)


def test_enqueued_translation_job_reports_progress_via_report_progress(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {"translations": [{"text": "olá"}]},
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)
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
    in_memory_session.add(
        LanguageProfile(
            name="default",
            source_languages="en",
            target_languages="pt-BR",
            is_default=True,
        )
    )
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, tmp_path / "Foo" / "Foo.mkv")
    in_memory_session.commit()

    scheduler = build_scheduler()
    enqueue_translation(
        scheduler, media_file.id, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    assert progress_calls == [
        (
            f"subtitle_translation:{media_file.id}",
            {"phase": "translating", "current": 1, "total": 1, "language": "pt-BR"},
        )
    ]


def test_enqueued_translation_job_honors_manually_picked_source_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    """`source_subtitle_id` passed to `enqueue_translation` reaches `translate_media_file`
    through the job closure — here picking an `fr` subtitle the profile's `source_languages`
    ("en") wouldn't otherwise consider, to prove the override actually took effect."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {"translations": [{"text": "bonjour traduit"}]},
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)

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
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    (tmp_path / "Foo" / "Foo.fr.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nbonjour\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, tmp_path / "Foo" / "Foo.mkv")
    in_memory_session.commit()
    fr_subtitle = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file.id,
            Subtitle.language == "fr",
        )
    ).one()

    scheduler = build_scheduler()
    enqueue_translation(
        scheduler,
        media_file.id,
        JobQueue.TRANSLATE,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        source_subtitle_id=fr_subtitle.id,
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "bonjour traduit" in output.read_text(encoding="utf-8")


def test_enqueue_full_translation_scan_enqueues_media_files_that_need_translation(
    in_memory_session, tmp_path, monkeypatch
):
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

    not_yet_scanned = MediaFile(
        movie_id=movie.id, relative_path="Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    needs_translation_file = MediaFile(
        movie_id=movie.id, relative_path="Bar.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    fully_covered = MediaFile(
        movie_id=movie.id, relative_path="Baz.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    in_memory_session.add(not_yet_scanned)
    in_memory_session.add(needs_translation_file)
    in_memory_session.add(fully_covered)
    in_memory_session.commit()
    assert needs_translation_file.id is not None
    assert fully_covered.id is not None
    # `not_yet_scanned` is never passed to `scan_subtitles_for_media_file` below, so it
    # has no `SubtitleScanState` row — discovery hasn't run for it yet.

    (tmp_path / "Bar").mkdir()
    (tmp_path / "Bar" / "Bar.mkv").touch()
    (tmp_path / "Bar" / "Bar.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(
        in_memory_session, needs_translation_file, tmp_path / "Bar" / "Bar.mkv"
    )

    (tmp_path / "Baz").mkdir()
    (tmp_path / "Baz" / "Baz.mkv").touch()
    (tmp_path / "Baz" / "Baz.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    (tmp_path / "Baz" / "Baz.pt-br.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nolá\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, fully_covered, tmp_path / "Baz" / "Baz.mkv")
    in_memory_session.commit()

    scheduler = build_scheduler()
    added = []
    monkeypatch.setattr(scheduler, "add_job", lambda *args, **kwargs: added.append((args, kwargs)))

    enqueued = enqueue_full_translation_scan(
        scheduler, in_memory_session, retry_attempts=1, retry_delay_seconds=0.0
    )

    assert enqueued == 1
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_translation:{needs_translation_file.id}"}
    assert all(kwargs["executor"] == JobQueue.TRANSLATE_BULK.value for _, kwargs in added)


def test_enqueued_translation_job_notifies_media_servers_after_write(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
    monkeypatch.setattr(
        ProviderHttpClient,
        "post_json",
        lambda self, path, json: {"translations": [{"text": "olá"}]},
    )
    monkeypatch.setattr(ProviderHttpClient, "close", lambda self: None)
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
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
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
    (tmp_path / "Foo" / "Foo.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nhello\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, tmp_path / "Foo" / "Foo.mkv")
    in_memory_session.commit()

    scheduler = build_scheduler()
    enqueue_translation(
        scheduler, media_file.id, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    assert notified == [tmp_path / "Foo" / "Foo.mkv"]


def test_enqueued_translation_job_does_not_notify_media_servers_on_skip(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(jobs_module, "get_session", _session)
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
    enqueue_translation(
        scheduler, media_file.id, JobQueue.TRANSLATE, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_translation:{media_file.id}")
    assert job is not None
    job.func()

    assert notified == []
