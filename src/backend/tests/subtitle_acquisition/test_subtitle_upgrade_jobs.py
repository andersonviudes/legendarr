from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.config.config_file import AppConfigFile
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_acquisition import upgrade_jobs as upgrade_jobs_module
from legendarr_backend.subtitle_acquisition import (
    upgrade_media_file_subtitle as upgrade_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    CandidateEvaluation,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.upgrade_jobs import (
    enqueue_full_upgrade_scan,
    enqueue_upgrade,
    register_subtitle_upgrade_job,
)
from legendarr_backend.subtitle_discovery.models import Subtitle, SubtitleScanState
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


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


def _existing_subtitle_media_file(session, tmp_path):
    """A movie's `MediaFile` with an already-acquired source-language subtitle on disk —
    the shared fixture shape both upgrade tests below start from."""
    service = _arr_service(session, tmp_path)
    assert service.id is not None
    movie = Movie(arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo")
    session.add(movie)
    session.add(
        LanguageProfile(
            name="default",
            source_languages="en",
            target_languages="pt-BR",
            is_default=True,
        )
    )
    session.commit()
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    assert media_file.id is not None
    (tmp_path / "Foo").mkdir()
    (tmp_path / "Foo" / "Foo.mkv").touch()
    (tmp_path / "Foo" / "Foo.en.srt").write_text("old", encoding="utf-8")
    session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo.en.srt",
            content_hash="old-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    session.commit()
    record_acquired_subtitle(
        session,
        media_file.id,
        "en",
        provider="old-provider",
        release_name="Foo.OLD",
        download_id="old-1",
        evaluation=CandidateEvaluation(score=0.1, title_similarity=0.1, attribute_matches={}),
    )
    session.commit()
    return media_file


def test_register_subtitle_upgrade_job_wires_config_derived_policy():
    scheduler = build_scheduler()
    config = AppConfigFile(
        upgrade_interval_minutes=45,
        upgrade_max_instances=2,
        upgrade_coalesce=False,
    )

    register_subtitle_upgrade_job(scheduler, config)

    job = scheduler.get_job("subtitle_upgrade_fanout")
    assert job is not None
    assert job.executor == JobQueue.UPGRADE_BULK.value
    assert job.max_instances == 2
    assert job.coalesce is False
    assert job.trigger.interval.total_seconds() == 45 * 60


def test_enqueued_upgrade_job_upgrades_an_existing_source_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    """The upgrade job re-searches providers for a media file's already-acquired
    subtitle and replaces it in place — ROADMAP 0.12.0's upgrade/replace pass, now its
    own job independent of acquisition."""

    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(upgrade_jobs_module, "get_session", _session)
    monkeypatch.setattr(
        upgrade_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )

    media_file = _existing_subtitle_media_file(in_memory_session, tmp_path)
    assert media_file.id is not None

    scheduler = build_scheduler()
    enqueue_upgrade(
        scheduler, media_file.id, JobQueue.UPGRADE_BULK, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_upgrade:{media_file.id}")
    assert job is not None
    job.func()

    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hi" in output.read_text(encoding="utf-8")


def test_enqueued_upgrade_job_notifies_media_servers_after_upgrade(
    in_memory_session, tmp_path, monkeypatch
):
    @contextmanager
    def _session():
        yield in_memory_session

    monkeypatch.setattr(upgrade_jobs_module, "get_session", _session)
    monkeypatch.setattr(
        upgrade_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )
    notified = []
    monkeypatch.setattr(
        upgrade_jobs_module,
        "notify_media_servers_of_subtitle_write",
        lambda session, video_path: notified.append(video_path),
    )

    media_file = _existing_subtitle_media_file(in_memory_session, tmp_path)
    assert media_file.id is not None

    scheduler = build_scheduler()
    enqueue_upgrade(
        scheduler, media_file.id, JobQueue.UPGRADE_BULK, retry_attempts=1, retry_delay_seconds=0.0
    )
    job = scheduler.get_job(f"subtitle_upgrade:{media_file.id}")
    assert job is not None
    job.func()

    assert notified == [tmp_path / "Foo" / "Foo.mkv"]


def test_enqueue_full_upgrade_scan_enqueues_every_known_media_file(
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

    enqueued = enqueue_full_upgrade_scan(
        scheduler,
        in_memory_session,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        recheck_after=timedelta(hours=24),
    )

    assert enqueued == 2
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_upgrade:{first.id}", f"subtitle_upgrade:{second.id}"}
    assert all(kwargs["executor"] == JobQueue.UPGRADE_BULK.value for _, kwargs in added)


def test_enqueue_full_upgrade_scan_skips_media_file_without_subtitle_scan(
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

    enqueued = enqueue_full_upgrade_scan(
        scheduler,
        in_memory_session,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        recheck_after=timedelta(hours=24),
    )

    assert enqueued == 1
    ids = {kwargs["id"] for _, kwargs in added}
    assert ids == {f"subtitle_upgrade:{scanned.id}"}
