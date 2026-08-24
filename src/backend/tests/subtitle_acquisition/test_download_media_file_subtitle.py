from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition import (
    download_media_file_subtitle as download_module,
)
from legendarr_backend.subtitle_acquisition.download_media_file_subtitle import (
    download_subtitle_candidate,
)
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate
from legendarr_backend.subtitle_discovery.models import Subtitle
from sqlmodel import select


class _FakeProvider:
    def __init__(self, name: str, text: str = "1\n00:00:00,000 --> 00:00:15,000\nHi\n\n"):
        self.name = name
        self.text = text

    def search(self, *args, **kwargs):
        raise NotImplementedError

    def download(self, result):
        return self.text


class _FailingDownloadProvider:
    name = "failing"

    def search(self, *args, **kwargs):
        raise NotImplementedError

    def download(self, result):
        raise RuntimeError("boom")


def _movie(session, tmp_path: Path) -> Movie:
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
        title="Foo",
        remote_path="/remote/Foo",
        imdb_id="tt1234567",
    )
    session.add(movie)
    session.commit()
    return movie


def _media_file(session, movie: Movie) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _write_video(tmp_path: Path) -> Path:
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    return video


def _use_chain(monkeypatch, *providers):
    monkeypatch.setattr(
        download_module, "resolve_subtitle_provider_chain", lambda session: list(providers)
    )


def _candidate(**overrides) -> SubtitleCandidate:
    data = {
        "provider": "provider",
        "release_name": "Foo",
        "download_id": "1",
        "language": "en",
        "page_link": None,
    }
    data.update(overrides)
    return SubtitleCandidate(**data)


def test_download_writes_the_file_and_rescans(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FakeProvider("provider"))

    success, message = download_subtitle_candidate(
        in_memory_session, media_file, video, _candidate(), "en"
    )

    assert success is True
    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hi" in output.read_text(encoding="utf-8")
    rows = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert any(row.language == "en" for row in rows)


def test_download_returns_false_when_the_provider_is_no_longer_in_the_chain(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FakeProvider("some-other-provider"))

    success, message = download_subtitle_candidate(
        in_memory_session, media_file, video, _candidate(provider="gone"), "en"
    )

    assert success is False
    assert not (tmp_path / "Foo" / "Foo.en.srt").exists()


def test_download_returns_false_on_a_provider_exception(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FailingDownloadProvider())

    success, message = download_subtitle_candidate(
        in_memory_session, media_file, video, _candidate(provider="failing"), "en"
    )

    assert success is False
    assert not (tmp_path / "Foo" / "Foo.en.srt").exists()


def test_download_returns_false_when_the_content_fails_the_quality_gate(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FakeProvider("provider", text="too short to be a real subtitle"))

    success, message = download_subtitle_candidate(
        in_memory_session, media_file, video, _candidate(), "en"
    )

    assert success is False
    assert not (tmp_path / "Foo" / "Foo.en.srt").exists()
