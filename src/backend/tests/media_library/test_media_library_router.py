from datetime import UTC, datetime
from functools import partial

from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_clients.sonarr_client import SonarrClient
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.queues import JobQueue
from legendarr_backend.scheduling.scheduler import build_scheduler
from legendarr_backend.subtitle_acquisition import (
    download_media_file_subtitle as download_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition import (
    search_media_file_subtitle as search_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_discovery.jobs import enqueue_subtitle_scan
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from sqlmodel import select


def _seed_movie() -> Movie:
    with get_session() as session:
        arr_service = ArrService(
            name="radarr", service_type="radarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        assert arr_service.id is not None
        movie = Movie(
            arr_service_id=arr_service.id,
            arr_id=1,
            title="Foo",
            remote_path="/movies/Foo",
            monitored=True,
            status="released",
            quality_profile_name="Any",
        )
        session.add(movie)
        session.commit()
        session.refresh(movie)
        return movie


def _seed_series() -> Series:
    with get_session() as session:
        arr_service = ArrService(
            name="sonarr", service_type="sonarr", host="h", port=1, api_key="k"
        )
        session.add(arr_service)
        session.commit()
        session.refresh(arr_service)
        assert arr_service.id is not None
        series = Series(
            arr_service_id=arr_service.id,
            arr_id=7,
            title="Bar",
            remote_path="/tv/Bar",
            monitored=True,
            status="continuing",
            quality_profile_name="Any",
            episode_count=8,
            episode_file_count=8,
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        return series


def test_get_movies_returns_empty_list_with_nothing_synced(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/movies")

    assert response.status_code == 200
    assert response.json() == []


def test_get_movies_returns_persisted_movies(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed_movie()
        response = client.get("/media/movies")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Foo"
    assert body[0]["monitored"] is True
    assert body[0]["quality_profile_name"] == "Any"


def test_get_series_returns_persisted_series_with_episode_counts(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed_series()
        response = client.get("/media/series")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Bar"
    assert body[0]["episode_count"] == 8
    assert body[0]["episode_file_count"] == 8


def test_get_movie_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/movies/1")

    assert response.status_code == 404


def test_get_wanted_returns_empty_list_with_nothing_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        _seed_movie()
        response = client.get("/media/wanted")

    assert response.status_code == 200
    assert response.json() == []


def test_get_movie_returns_detail_with_files(isolated_database):
    with TestClient(create_api_app()) as client:
        movie = _seed_movie()
        response = client.get(f"/media/movies/{movie.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Foo"
    assert body["files"] == []
    assert body["missing_subtitles_count"] == 0


def test_get_series_item_returns_404_when_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/series/1")

    assert response.status_code == 404


def test_get_series_item_returns_detail_with_episodes(isolated_database, monkeypatch):
    monkeypatch.setattr(SonarrClient, "list_episodes", lambda self, series_id: [])

    with TestClient(create_api_app()) as client:
        series = _seed_series()
        response = client.get(f"/media/series/{series.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Bar"
    assert body["episodes"] == []


def test_trigger_movie_scan_enqueues_media_scan(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    app.state.cascade_subtitle_scan = partial(
        enqueue_subtitle_scan,
        scheduler,
        queue=JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            session.add(
                MediaFile(
                    movie_id=movie.id,
                    relative_path="Foo.mkv",
                    size_bytes=1,
                    scanned_at=datetime.now(UTC),
                )
            )
            session.commit()
        response = client.post(f"/media/movies/{movie.id}/scan")

    assert response.status_code == 202
    assert scheduler.get_job(f"media_scan:movie:{movie.id}") is not None


def test_trigger_movie_scan_cascades_to_subtitle_scan_for_new_file(isolated_database, tmp_path):
    """ "Scan Disk" now closes its own documented gap: a file the scan itself just
    discovered on disk is picked up too, not just files that already existed."""
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler
    app.state.cascade_subtitle_scan = partial(
        enqueue_subtitle_scan,
        scheduler,
        queue=JobQueue.SCAN,
        retry_attempts=1,
        retry_delay_seconds=0.0,
        cascade=True,
    )

    with TestClient(app) as client:
        with get_session() as session:
            arr_service = ArrService(
                name="radarr",
                service_type="radarr",
                host="h",
                port=1,
                api_key="k",
                remote_path_prefix="/remote",
                local_path_prefix=str(tmp_path),
            )
            session.add(arr_service)
            session.commit()
            session.refresh(arr_service)
            assert arr_service.id is not None
            movie = Movie(
                arr_service_id=arr_service.id,
                arr_id=1,
                title="Foo",
                remote_path="/remote/Foo",
            )
            session.add(movie)
            session.commit()
            session.refresh(movie)
            movie_id = movie.id
        video = tmp_path / "Foo" / "Foo.mkv"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"x" * 42)

        response = client.post(f"/media/movies/{movie_id}/scan")
        assert response.status_code == 202
        job = scheduler.get_job(f"media_scan:movie:{movie_id}")
        assert job is not None
        job.func()

    with get_session() as session:
        media_files = list(session.exec(select(MediaFile)).all())
    assert len(media_files) == 1
    assert scheduler.get_job(f"subtitle_scan:{media_files[0].id}") is not None


def test_trigger_movie_scan_without_scheduler_returns_503(isolated_database):
    with TestClient(create_api_app()) as client:
        movie = _seed_movie()
        response = client.post(f"/media/movies/{movie.id}/scan")

    assert response.status_code == 503


def test_trigger_movie_scan_without_cascade_callback_returns_503(isolated_database):
    app = create_api_app()
    app.state.scheduler = build_scheduler()

    with TestClient(app) as client:
        movie = _seed_movie()
        response = client.post(f"/media/movies/{movie.id}/scan")

    assert response.status_code == 503


def test_trigger_file_translation_enqueues_translation(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            media_file = MediaFile(
                movie_id=movie.id,
                relative_path="Foo.mkv",
                size_bytes=1,
                scanned_at=datetime.now(UTC),
            )
            session.add(media_file)
            session.commit()
            session.refresh(media_file)
            media_file_id = media_file.id
        response = client.post(f"/media/files/{media_file_id}/translate")

    assert response.status_code == 202
    assert scheduler.get_job(f"subtitle_translation:{media_file_id}") is not None


def test_trigger_file_translation_returns_404_when_missing(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        response = client.post("/media/files/1/translate")

    assert response.status_code == 404


def test_trigger_subtitle_timing_sync_enqueues_sync(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            media_file = MediaFile(
                movie_id=movie.id,
                relative_path="Foo.mkv",
                size_bytes=1,
                scanned_at=datetime.now(UTC),
            )
            session.add(media_file)
            session.commit()
            session.refresh(media_file)
            assert media_file.id is not None
            subtitle = Subtitle(
                media_file_id=media_file.id,
                language="en",
                origin=SubtitleOrigin.EXTERNAL,
                relative_path="Foo.en.srt",
                content_hash="test-hash",
                scanned_at=datetime.now(UTC),
            )
            session.add(subtitle)
            session.commit()
            session.refresh(subtitle)
            subtitle_id = subtitle.id
        response = client.post(f"/media/subtitles/{subtitle_id}/sync-timing")

    assert response.status_code == 202
    assert scheduler.get_job(f"subtitle_timing_sync:{subtitle_id}") is not None


def test_trigger_subtitle_timing_sync_returns_404_when_missing(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        response = client.post("/media/subtitles/1/sync-timing")

    assert response.status_code == 404


def test_trigger_subtitle_source_translation_enqueues_translation(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        movie = _seed_movie()
        with get_session() as session:
            media_file = MediaFile(
                movie_id=movie.id,
                relative_path="Foo.mkv",
                size_bytes=1,
                scanned_at=datetime.now(UTC),
            )
            session.add(media_file)
            session.commit()
            session.refresh(media_file)
            assert media_file.id is not None
            subtitle = Subtitle(
                media_file_id=media_file.id,
                language="en",
                origin=SubtitleOrigin.EXTERNAL,
                relative_path="Foo.en.srt",
                content_hash="test-hash",
                scanned_at=datetime.now(UTC),
            )
            session.add(subtitle)
            session.commit()
            session.refresh(subtitle)
            subtitle_id = subtitle.id
            media_file_id = media_file.id
        response = client.post(f"/media/subtitles/{subtitle_id}/translate")

    assert response.status_code == 202
    assert scheduler.get_job(f"subtitle_translation:{media_file_id}") is not None


def test_trigger_subtitle_source_translation_returns_404_when_missing(isolated_database):
    app = create_api_app()
    scheduler = build_scheduler()
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        response = client.post("/media/subtitles/1/translate")

    assert response.status_code == 404


class _FakeProvider:
    name = "fake"

    def __init__(self, results=None, text="1\n00:00:00,000 --> 00:00:01,000\nHi\n\n"):
        self.results = (
            results
            if results is not None
            else [SubtitleSearchResult(release_name="Foo", download_id="1", language="en")]
        )
        self.text = text

    def search(self, *args, **kwargs):
        return self.results

    def download(self, result):
        return self.text


def _seed_movie_with_video(tmp_path) -> int:
    with get_session() as session:
        service = create_arr_service(
            session,
            ArrServiceInput(
                name="radarr",
                service_type="radarr",
                host="h",
                port=1,
                api_key="k",
                remote_path_prefix="/remote",
                local_path_prefix=str(tmp_path),
            ),
        )
        assert service.id is not None
        movie = Movie(
            arr_service_id=service.id,
            arr_id=1,
            title="Foo",
            remote_path="/remote/Foo",
            imdb_id="tt1234567",
        )
        session.add(movie)
        session.commit()
        session.refresh(movie)
        assert movie.id is not None
        media_file = MediaFile(
            movie_id=movie.id,
            relative_path="Foo.mkv",
            size_bytes=1,
            scanned_at=datetime.now(UTC),
        )
        session.add(media_file)
        session.commit()
        session.refresh(media_file)
        assert media_file.id is not None
        media_file_id = media_file.id
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    return media_file_id


def test_search_subtitle_candidates_returns_candidates_from_the_provider_chain(
    isolated_database, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        search_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )

    with TestClient(create_api_app()) as client:
        media_file_id = _seed_movie_with_video(tmp_path)
        response = client.get(
            f"/media/files/{media_file_id}/subtitle-candidates", params={"language": "en"}
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["provider"] == "fake"
    assert body[0]["download_id"] == "1"


def test_search_subtitle_candidates_returns_404_when_media_file_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/media/files/1/subtitle-candidates", params={"language": "en"})

    assert response.status_code == 404


def test_download_subtitle_candidate_writes_the_file(isolated_database, tmp_path, monkeypatch):
    monkeypatch.setattr(
        download_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: [_FakeProvider()],
    )

    with TestClient(create_api_app()) as client:
        media_file_id = _seed_movie_with_video(tmp_path)
        response = client.post(
            f"/media/files/{media_file_id}/subtitle-candidates/download",
            json={
                "provider": "fake",
                "release_name": "Foo",
                "download_id": "1",
                "language": "pt",
                "target_language": "pt-BR",
                "page_link": None,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # The sidecar is named after the searched language, not the provider-reported one.
    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "Hi" in output.read_text(encoding="utf-8")
    # The route owns the commit — a fresh session must see the scanned Subtitle row.
    with get_session() as session:
        persisted = session.exec(
            select(Subtitle).where(Subtitle.media_file_id == media_file_id)
        ).all()
    assert any(subtitle.language == "pt-br" for subtitle in persisted)


def test_download_subtitle_candidate_returns_404_when_media_file_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post(
            "/media/files/1/subtitle-candidates/download",
            json={
                "provider": "fake",
                "release_name": "Foo",
                "download_id": "1",
                "language": "en",
                "target_language": "en",
                "page_link": None,
            },
        )

    assert response.status_code == 404


def test_upload_subtitle_writes_the_file(isolated_database, tmp_path):
    with TestClient(create_api_app()) as client:
        media_file_id = _seed_movie_with_video(tmp_path)
        response = client.post(
            f"/media/files/{media_file_id}/subtitle-upload",
            data={"language": "en"},
            files={"file": ("uploaded.srt", b"content", "text/plain")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert any(subtitle["language"] == "en" for subtitle in body["subtitles"])
    output = tmp_path / "Foo" / "Foo.en.srt"
    assert output.read_bytes() == b"content"
    # The route owns the commit — a fresh session must see the scanned Subtitle row.
    with get_session() as session:
        persisted = session.exec(
            select(Subtitle).where(Subtitle.media_file_id == media_file_id)
        ).all()
    assert any(subtitle.language == "en" for subtitle in persisted)


def test_upload_subtitle_returns_404_when_media_file_missing(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.post(
            "/media/files/1/subtitle-upload",
            data={"language": "en"},
            files={"file": ("uploaded.srt", b"content", "text/plain")},
        )

    assert response.status_code == 404
