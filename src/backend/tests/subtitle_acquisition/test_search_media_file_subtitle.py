from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.scheduling.circuit_breaker import (
    FAILURE_THRESHOLD,
    BreakerCategory,
    is_open,
    record_failure,
)
from legendarr_backend.subtitle_acquisition import search_context as search_context_module
from legendarr_backend.subtitle_acquisition import search_media_file_subtitle as search_module
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import (
    search_media_file_subtitle_candidates,
)


class _FakeProvider:
    def __init__(self, name: str, results=None):
        self.name = name
        self.results = results if results is not None else []

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
    ):
        return self.results

    def download(self, result):
        raise NotImplementedError


class _FailingProvider:
    name = "failing"

    def __init__(self):
        self.search_calls = []

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
    ):
        self.search_calls.append({"title": title, "language": language})
        raise RuntimeError("boom")

    def download(self, result):
        raise NotImplementedError


def _movie(session, tmp_path: Path, **overrides) -> Movie:
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
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo",
        "remote_path": "/remote/Foo",
        "imdb_id": "tt1234567",
    }
    data.update(overrides)
    movie = Movie(**data)
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


def _series(session, tmp_path: Path, **overrides) -> Series:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr",
            service_type="sonarr",
            host="sonarr",
            port=8989,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo",
        "remote_path": "/remote/Foo",
    }
    data.update(overrides)
    series = Series(**data)
    session.add(series)
    session.commit()
    return series


def _series_media_file(session, series: Series) -> MediaFile:
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Foo/Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _use_chain(monkeypatch, *providers):
    monkeypatch.setattr(
        search_module, "resolve_subtitle_provider_chain", lambda session: list(providers)
    )


def test_search_returns_empty_list_for_an_empty_chain(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert result == []


def test_search_aggregates_candidates_from_every_provider(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    provider_a = _FakeProvider(
        "provider-a",
        results=[SubtitleSearchResult(release_name="Foo.2024", download_id="1", language="en")],
    )
    provider_b = _FakeProvider(
        "provider-b",
        results=[
            SubtitleSearchResult(release_name="Foo.2024.EXTENDED", download_id="2", language="en")
        ],
    )
    _use_chain(monkeypatch, provider_a, provider_b)

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert {candidate.provider for candidate in result} == {"provider-a", "provider-b"}
    assert {candidate.download_id for candidate in result} == {"1", "2"}


def test_search_sorts_candidates_by_score_descending(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            ),
            SubtitleSearchResult(release_name="Foo", download_id="2", language="en"),
        ],
    )
    _use_chain(monkeypatch, provider)

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert [candidate.download_id for candidate in result] == ["2", "1"]
    assert result[0].score >= result[1].score


def test_search_skips_a_failing_provider_and_keeps_going(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    working = _FakeProvider(
        "working",
        results=[SubtitleSearchResult(release_name="Foo", download_id="1", language="en")],
    )
    _use_chain(monkeypatch, _FailingProvider(), working)

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert len(result) == 1
    assert result[0].provider == "working"


def test_search_skips_a_provider_with_an_open_circuit(
    in_memory_session, tmp_path, monkeypatch, isolated_circuit_breakers
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    failing = _FailingProvider()
    working = _FakeProvider(
        "working",
        results=[SubtitleSearchResult(release_name="Foo", download_id="1", language="en")],
    )
    _use_chain(monkeypatch, failing, working)
    for _ in range(FAILURE_THRESHOLD):
        record_failure(BreakerCategory.ACQUISITION, failing.name)

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert len(result) == 1
    assert result[0].provider == "working"
    assert failing.search_calls == []


def test_search_opens_the_circuit_after_repeated_failures(
    in_memory_session, tmp_path, monkeypatch, isolated_circuit_breakers
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FailingProvider())

    for _ in range(FAILURE_THRESHOLD):
        search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    assert is_open(BreakerCategory.ACQUISITION, "failing") is True


def test_search_excludes_a_wrong_episode_candidate(in_memory_session, tmp_path, monkeypatch):
    series = _series(in_memory_session, tmp_path)
    media_file = _series_media_file(in_memory_session, series)
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(
                release_name="Foo.S01E03.WEB-DL", download_id="wrong", language="en"
            ),
            SubtitleSearchResult(
                release_name="Foo.S01E02.WEB-DL", download_id="right", language="en"
            ),
        ],
    )
    _use_chain(monkeypatch, provider)
    monkeypatch.setattr(
        search_context_module,
        "resolve_media_file_episode",
        lambda session, media_file: EpisodeItem(
            season_number=1, episode_number=2, title="Foo", relative_path="Foo/Foo.mkv"
        ),
    )

    result = search_media_file_subtitle_candidates(in_memory_session, media_file, video, "en")

    # A manual search stays exhaustive for everything else, but a candidate naming a
    # detectably wrong episode is still excluded — confirmed with the user this gate
    # applies uniformly, not just to the automatic acquire/upgrade paths.
    assert [candidate.download_id for candidate in result] == ["right"]
