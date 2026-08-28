from datetime import UTC, datetime

from fastapi.testclient import TestClient
from legendarr_backend.api import create_api_app
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_translation.models import TranslationFailure


def test_get_history_returns_empty_list_with_no_data(isolated_database):
    with TestClient(create_api_app()) as client:
        response = client.get("/history")

    assert response.status_code == 200
    assert response.json() == []


def test_get_history_reflects_a_recorded_failure(isolated_database, tmp_path):
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
            session.add(
                TranslationFailure(
                    media_file_id=media_file.id,
                    source_language="en",
                    target_language="pt-BR",
                    error_message="deepl: invalid API key",
                    failed_at=datetime.now(UTC),
                )
            )
            session.commit()

        response = client.get("/history")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["category"] == "translation"
    assert body[0]["status"] == "failure"
    assert body[0]["media_title"] == "Foo"
    assert body[0]["error_message"] == "deepl: invalid API key"


def test_get_history_respects_the_limit_query_param(isolated_database, tmp_path):
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
            for target_language in ["pt-BR", "es"]:
                session.add(
                    TranslationFailure(
                        media_file_id=media_file.id,
                        source_language="en",
                        target_language=target_language,
                        error_message="deepl: invalid API key",
                        failed_at=datetime.now(UTC),
                    )
                )
            session.commit()

        response = client.get("/history", params={"limit": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1
