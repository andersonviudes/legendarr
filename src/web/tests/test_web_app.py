from fastapi.testclient import TestClient
from legendarr_web.app import create_app
from legendarr_web.config.settings import get_web_settings


def test_posters_mount_serves_a_cached_poster_file():
    posters_dir = get_web_settings().data_dir / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    (posters_dir / "movie_1.jpg").write_bytes(b"fake-jpeg-bytes")
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/posters/movie_1.jpg")

    assert response.status_code == 200
    assert response.content == b"fake-jpeg-bytes"


def test_posters_mount_404s_for_an_uncached_poster():
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/posters/movie_999999.jpg")

    assert response.status_code == 404
