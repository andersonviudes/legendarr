from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.media_library.scan_media_files import delete_media_files, scan_media_item
from sqlmodel import select


def _create_service(session, tmp_path: Path, name: str, service_type: str) -> ArrService:
    return create_arr_service(
        session,
        ArrServiceInput(
            name=name,
            service_type=service_type,
            host=name,
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )


def _movie(session, arr_service, **overrides) -> Movie:
    movie = Movie(
        arr_service_id=arr_service.id,
        arr_id=overrides.get("arr_id", 1),
        title=overrides.get("title", "Foo"),
        remote_path=overrides.get("remote_path", "/remote/Foo"),
    )
    session.add(movie)
    session.commit()
    return movie


def _series(session, arr_service, **overrides) -> Series:
    series = Series(
        arr_service_id=arr_service.id,
        arr_id=overrides.get("arr_id", 1),
        title=overrides.get("title", "Bar"),
        remote_path=overrides.get("remote_path", "/remote/Bar"),
    )
    session.add(series)
    session.commit()
    return series


def _video(root: Path, relative: str, size: int = 10) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def _files(session) -> list[MediaFile]:
    return list(session.exec(select(MediaFile)).all())


def test_scan_persists_video_files_relative_to_item_root(in_memory_session, tmp_path):
    service = _create_service(in_memory_session, tmp_path, "radarr", "radarr")
    movie = _movie(in_memory_session, service)
    _video(tmp_path, "Foo/Foo.2024.mkv", size=100)

    result = scan_media_item(in_memory_session, movie, service)
    in_memory_session.commit()

    assert result.added == 1
    assert result.removed == 0
    assert result.skipped is False
    row = _files(in_memory_session)[0]
    assert row.movie_id == movie.id
    assert row.series_id is None
    assert row.relative_path == "Foo.2024.mkv"
    assert row.size_bytes == 100
    assert row.scanned_at is not None


def test_scan_walks_series_subfolders(in_memory_session, tmp_path):
    service = _create_service(in_memory_session, tmp_path, "sonarr", "sonarr")
    series = _series(in_memory_session, service)
    _video(tmp_path, "Bar/Season 01/Bar.S01E01.mkv")
    _video(tmp_path, "Bar/Season 02/Bar.S02E01.mkv")

    result = scan_media_item(in_memory_session, series, service)
    in_memory_session.commit()

    assert result.added == 2
    paths = {row.relative_path for row in _files(in_memory_session)}
    assert paths == {"Season 01/Bar.S01E01.mkv", "Season 02/Bar.S02E01.mkv"}
    assert all(row.series_id == series.id for row in _files(in_memory_session))


def test_scan_ignores_samples_and_non_video_files(in_memory_session, tmp_path):
    service = _create_service(in_memory_session, tmp_path, "radarr", "radarr")
    movie = _movie(in_memory_session, service)
    _video(tmp_path, "Foo/Foo.mkv")
    _video(tmp_path, "Foo/Foo.sample.mkv")
    (tmp_path / "Foo" / "Foo.srt").write_text("subtitle")
    (tmp_path / "Foo" / "notes.txt").write_text("x")

    result = scan_media_item(in_memory_session, movie, service)
    in_memory_session.commit()

    assert result.added == 1
    assert _files(in_memory_session)[0].relative_path == "Foo.mkv"


def test_rescan_updates_changed_sizes_and_removes_missing(in_memory_session, tmp_path):
    service = _create_service(in_memory_session, tmp_path, "radarr", "radarr")
    movie = _movie(in_memory_session, service)
    kept = _video(tmp_path, "Foo/Foo.mkv", size=10)
    _video(tmp_path, "Foo/extra.mkv", size=20)
    scan_media_item(in_memory_session, movie, service)
    in_memory_session.commit()

    kept.write_bytes(b"x" * 99)
    (tmp_path / "Foo" / "extra.mkv").unlink()
    result = scan_media_item(in_memory_session, movie, service)
    in_memory_session.commit()

    assert result.added == 0
    assert result.size_changed == 1
    assert result.removed == 1
    rows = _files(in_memory_session)
    assert len(rows) == 1
    assert rows[0].relative_path == "Foo.mkv"
    assert rows[0].size_bytes == 99


def test_scan_with_missing_root_skips_and_keeps_rows(in_memory_session, tmp_path):
    """An unmounted drive must look different from deleted files — rows are kept."""
    service = _create_service(in_memory_session, tmp_path, "radarr", "radarr")
    movie = _movie(in_memory_session, service, remote_path="/remote/Gone")
    in_memory_session.add(
        MediaFile(
            movie_id=movie.id,
            relative_path="Gone.mkv",
            size_bytes=5,
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    result = scan_media_item(in_memory_session, movie, service)

    assert result.skipped is True
    assert result.added == 0
    assert result.removed == 0
    assert len(_files(in_memory_session)) == 1


def test_delete_media_files_removes_only_the_items_rows(in_memory_session, tmp_path):
    service = _create_service(in_memory_session, tmp_path, "radarr", "radarr")
    movie = _movie(in_memory_session, service, arr_id=1)
    other = _movie(in_memory_session, service, arr_id=2, title="Other")
    now = datetime.now(UTC)
    in_memory_session.add(
        MediaFile(movie_id=movie.id, relative_path="a.mkv", size_bytes=1, scanned_at=now)
    )
    in_memory_session.add(
        MediaFile(movie_id=other.id, relative_path="b.mkv", size_bytes=1, scanned_at=now)
    )
    in_memory_session.commit()

    removed = delete_media_files(in_memory_session, movie)
    in_memory_session.commit()

    assert removed == 1
    rows = _files(in_memory_session)
    assert len(rows) == 1
    assert rows[0].movie_id == other.id
