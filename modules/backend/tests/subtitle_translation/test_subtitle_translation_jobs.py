from contextlib import contextmanager
from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
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
    scheduler.get_job("subtitle_translation:999").func()


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
    scheduler.get_job(f"subtitle_translation:{media_file.id}").func()

    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "olá" in output.read_text(encoding="utf-8")
    rows = list(in_memory_session.exec(select(Subtitle)).all())
    assert any(row.language == "pt-br" for row in rows)


def test_enqueue_full_translation_scan_enqueues_every_known_media_file(
    in_memory_session, tmp_path, monkeypatch
):
    service = _arr_service(in_memory_session, tmp_path)
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

    enqueued = enqueue_full_translation_scan(
        scheduler, in_memory_session, retry_attempts=1, retry_delay_seconds=0.0
    )

    assert enqueued == 2
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_translation:{first.id}", f"subtitle_translation:{second.id}"}
    assert all(kwargs["executor"] == JobQueue.TRANSLATE_BULK.value for _, kwargs in added)
