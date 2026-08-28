import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.maintenance import cleanup_temp_files
from legendarr_backend.media_library.models import MediaFile, Movie


def _seed_arr_service(session) -> ArrService:
    arr_service = ArrService(name="radarr", service_type="radarr", host="h", port=1, api_key="k")
    session.add(arr_service)
    session.commit()
    session.refresh(arr_service)
    assert arr_service.id is not None
    return arr_service


def _seed_movie(session, arr_service, remote_path: str) -> Movie:
    movie = Movie(
        arr_service_id=arr_service.id,
        arr_id=1,
        title="A Movie",
        remote_path=remote_path,
        imdb_id="tt1",
    )
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def _seed_media_file(session, movie) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id, relative_path="Movie.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    session.add(media_file)
    session.commit()
    session.refresh(media_file)
    return media_file


def _touch(path: Path, *, age_minutes: float) -> None:
    path.write_bytes(b"x")
    stamp = (datetime.now(UTC) - timedelta(minutes=age_minutes)).timestamp()
    os.utime(path, (stamp, stamp))


def test_cleanup_orphaned_temp_files_removes_every_known_temp_suffix(in_memory_session, tmp_path):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service, str(tmp_path))
    _seed_media_file(session, movie)
    _touch(tmp_path / "Movie.en.srt.tmp", age_minutes=120)
    _touch(tmp_path / "Movie.en.srt.sup.tmp", age_minutes=120)
    _touch(tmp_path / "Movie.en.tmp.srt", age_minutes=120)
    _touch(tmp_path / "Movie.stt.tmp.wav", age_minutes=120)

    removed = cleanup_temp_files.cleanup_orphaned_temp_files(session, min_age_minutes=60)

    assert removed == 4
    assert list(tmp_path.iterdir()) == []


def test_cleanup_orphaned_temp_files_keeps_a_recent_temp_sibling(in_memory_session, tmp_path):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service, str(tmp_path))
    _seed_media_file(session, movie)
    _touch(tmp_path / "Movie.en.srt.tmp", age_minutes=1)

    removed = cleanup_temp_files.cleanup_orphaned_temp_files(session, min_age_minutes=60)

    assert removed == 0
    assert (tmp_path / "Movie.en.srt.tmp").exists()


def test_cleanup_orphaned_temp_files_ignores_unrelated_files(in_memory_session, tmp_path):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service, str(tmp_path))
    _seed_media_file(session, movie)
    _touch(tmp_path / "Movie.en.srt", age_minutes=120)

    removed = cleanup_temp_files.cleanup_orphaned_temp_files(session, min_age_minutes=60)

    assert removed == 0
    assert (tmp_path / "Movie.en.srt").exists()


def test_cleanup_orphaned_temp_files_skips_a_media_file_with_no_resolvable_path(
    in_memory_session, monkeypatch, tmp_path
):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service, str(tmp_path))
    _seed_media_file(session, movie)
    monkeypatch.setattr(cleanup_temp_files, "resolve_media_file_path", lambda *a, **k: None)

    removed = cleanup_temp_files.cleanup_orphaned_temp_files(session, min_age_minutes=60)

    assert removed == 0


def test_cleanup_orphaned_temp_files_tolerates_an_unmounted_directory(in_memory_session, tmp_path):
    session = in_memory_session
    arr_service = _seed_arr_service(session)
    movie = _seed_movie(session, arr_service, str(tmp_path / "missing"))
    _seed_media_file(session, movie)

    removed = cleanup_temp_files.cleanup_orphaned_temp_files(session, min_age_minutes=60)

    assert removed == 0
