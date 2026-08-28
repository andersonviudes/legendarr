from datetime import UTC, datetime

from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation.models import TranslationAttempt


def test_get_statistics_returns_empty_categories_with_no_data(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/statistics")

    assert response.status_code == 200
    body = response.json()
    assert body["translated"]["total"] == 0
    assert body["acquired"]["total"] == 0
    assert len(body["translated"]["daily"]) == 30


def test_get_statistics_reflects_a_recorded_translation_attempt(isolated_database, tmp_path):
    with TestClient(create_api_app()) as client:
        with get_session() as session:
            service = create_arr_service(
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
            assert service.id is not None
            movie = Movie(
                arr_service_id=service.id, arr_id=1, title="Foo", remote_path="/remote/Foo"
            )
            session.add(movie)
            session.commit()
            assert movie.id is not None
            media_file = MediaFile(
                movie_id=movie.id,
                relative_path="Foo/Foo.mkv",
                size_bytes=1,
                scanned_at=datetime.now(UTC),
            )
            session.add(media_file)
            session.commit()
            assert media_file.id is not None
            subtitle = Subtitle(
                media_file_id=media_file.id,
                language="pt-br",
                origin=SubtitleOrigin.EXTERNAL,
                relative_path="Foo/Foo.pt-br.srt",
                content_hash="hash",
                scanned_at=datetime.now(UTC),
            )
            session.add(subtitle)
            session.commit()
            assert subtitle.id is not None
            session.add(
                TranslationAttempt(
                    subtitle_id=subtitle.id,
                    provider="deepl",
                    source_language="en",
                    target_language="pt-BR",
                    translated_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.get("/statistics")

    assert response.status_code == 200
    body = response.json()
    assert body["translated"]["total"] == 1
    assert body["translated"]["by_provider"] == [{"label": "deepl", "count": 1}]
