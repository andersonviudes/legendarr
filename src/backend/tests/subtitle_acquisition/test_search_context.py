from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition import search_context as search_context_module
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context


def _movie_with_file(session, tmp_path: Path) -> tuple[MediaFile, Path]:
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
        arr_service_id=service.id,
        arr_id=1,
        title="Foo Bar",
        remote_path="/remote/Foo",
        imdb_id="tt1234567",
    )
    session.add(movie)
    session.commit()
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/video.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    video = tmp_path / "Foo" / "video.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00" * 65536)
    return media_file, video


def _configure_opensubtitles(session, **overrides) -> None:
    data = {"kind": "opensubtitles", "enabled": True, "username": "user", "password": "pass"}
    data.update(overrides)
    session.add(SubtitleProviderConfig(**data))
    session.commit()


def _refuse_to_hash(monkeypatch) -> None:
    """Reading the video is the one step here that touches the filesystem, and the whole
    point of gating it is that it never runs when nothing would search by the hash."""

    def _fail(path, **kwargs):
        raise AssertionError(f"the video at {path} should not have been hashed")

    monkeypatch.setattr(search_context_module, "compute_opensubtitles_hash", _fail)


def test_resolve_search_context_hashes_the_video_when_opensubtitles_wants_the_hash(
    in_memory_session, tmp_path
):
    media_file, video = _movie_with_file(in_memory_session, tmp_path)
    _configure_opensubtitles(in_memory_session)

    context = resolve_subtitle_search_context(in_memory_session, media_file, video)

    assert context.moviehash == "0000000000010000"


def test_resolve_search_context_skips_hashing_when_use_hash_is_disabled(
    in_memory_session, tmp_path, monkeypatch
):
    media_file, video = _movie_with_file(in_memory_session, tmp_path)
    _configure_opensubtitles(in_memory_session, use_hash=False)
    _refuse_to_hash(monkeypatch)

    context = resolve_subtitle_search_context(in_memory_session, media_file, video)

    assert context.moviehash is None


def test_resolve_search_context_skips_hashing_when_opensubtitles_is_disabled(
    in_memory_session, tmp_path, monkeypatch
):
    media_file, video = _movie_with_file(in_memory_session, tmp_path)
    _configure_opensubtitles(in_memory_session, enabled=False)
    _refuse_to_hash(monkeypatch)

    context = resolve_subtitle_search_context(in_memory_session, media_file, video)

    assert context.moviehash is None


def test_resolve_search_context_skips_hashing_when_opensubtitles_has_no_credentials(
    in_memory_session, tmp_path, monkeypatch
):
    media_file, video = _movie_with_file(in_memory_session, tmp_path)
    _configure_opensubtitles(in_memory_session, username=None, password=None)
    _refuse_to_hash(monkeypatch)

    context = resolve_subtitle_search_context(in_memory_session, media_file, video)

    assert context.moviehash is None


def test_resolve_search_context_skips_hashing_when_no_provider_is_configured(
    in_memory_session, tmp_path, monkeypatch
):
    media_file, video = _movie_with_file(in_memory_session, tmp_path)
    _refuse_to_hash(monkeypatch)

    context = resolve_subtitle_search_context(in_memory_session, media_file, video)

    assert context.moviehash is None
    assert context.title == "Foo Bar"
    assert context.imdb_id == "tt1234567"
