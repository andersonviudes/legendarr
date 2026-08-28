from pathlib import Path

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.config.settings import Settings
from legendarr_backend.media_library.models import Movie, Series
from legendarr_backend.media_metadata import poster_cache_cleanup


def _seed_arr_service(session) -> ArrService:
    arr_service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    assert arr_service.id is not None
    return arr_service


def _seed_movie(session, arr_service) -> Movie:
    movie = Movie(
        arr_service_id=arr_service.id, arr_id=1, title="A Movie", remote_path="/p", imdb_id="tt1"
    )
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def test_cleanup_orphaned_posters_is_a_noop_without_a_cache_dir(in_memory_session, monkeypatch):
    monkeypatch.setattr(
        poster_cache_cleanup,
        "get_settings",
        lambda: Settings(data_dir=Path("/nonexistent-dir-42")),
    )

    assert poster_cache_cleanup.cleanup_orphaned_posters(in_memory_session) == 0


def test_cleanup_orphaned_posters_removes_files_with_no_matching_movie_or_series(
    in_memory_session, monkeypatch, tmp_path
):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service)
    monkeypatch.setattr(poster_cache_cleanup, "get_settings", lambda: Settings(data_dir=tmp_path))
    posters_dir = tmp_path / "posters"
    posters_dir.mkdir()
    (posters_dir / f"movie_{movie.id}.jpg").write_bytes(b"live")
    (posters_dir / "movie_9999.jpg").write_bytes(b"orphaned")
    (posters_dir / "series_9999.jpg").write_bytes(b"orphaned")
    (posters_dir / "not-a-poster.txt").write_bytes(b"ignored")

    removed = poster_cache_cleanup.cleanup_orphaned_posters(session)

    assert removed == 2
    remaining = {path.name for path in posters_dir.iterdir()}
    assert remaining == {f"movie_{movie.id}.jpg", "not-a-poster.txt"}


def test_cleanup_orphaned_posters_keeps_files_for_a_live_series(
    in_memory_session, monkeypatch, tmp_path
):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    assert arr_service.id is not None
    series = Series(
        arr_service_id=arr_service.id,
        arr_id=1,
        title="A Series",
        remote_path="/p",
        imdb_id="tt2",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    monkeypatch.setattr(poster_cache_cleanup, "get_settings", lambda: Settings(data_dir=tmp_path))
    posters_dir = tmp_path / "posters"
    posters_dir.mkdir()
    (posters_dir / f"series_{series.id}.jpg").write_bytes(b"live")

    removed = poster_cache_cleanup.cleanup_orphaned_posters(session)

    assert removed == 0
    assert (posters_dir / f"series_{series.id}.jpg").exists()
