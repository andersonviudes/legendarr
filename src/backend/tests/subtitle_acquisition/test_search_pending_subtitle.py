from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition import search_pending_subtitle as search_module
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.search_pending_subtitle import (
    search_pending_subtitle_candidates,
)


class _FakeProvider:
    def __init__(self, name: str, results=None):
        self.name = name
        self.results = results if results is not None else []
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
        series_imdb_id=None,
    ):
        self.search_calls.append(
            {
                "season": season,
                "episode": episode,
                "video_path": video_path,
                "imdb_id": imdb_id,
                "series_imdb_id": series_imdb_id,
            }
        )
        return self.results

    def download(self, result):
        raise NotImplementedError


def _series(session) -> Series:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr",
            service_type="sonarr",
            host="sonarr",
            port=8989,
            api_key="api-key",
        ),
    )
    assert service.id is not None
    series = Series(
        arr_service_id=service.id,
        arr_id=7,
        title="Ahsoka",
        remote_path="/remote/Ahsoka",
        tvdb_id=123,
        imdb_id="tt1234567",
    )
    session.add(series)
    session.commit()
    return series


def _use_chain(monkeypatch, *providers):
    monkeypatch.setattr(
        search_module, "resolve_subtitle_provider_chain", lambda session: list(providers)
    )


def test_search_never_probes_a_video_file(in_memory_session, monkeypatch):
    series = _series(in_memory_session)
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(release_name="Ahsoka.S01E04", download_id="1", language="en")
        ],
    )
    _use_chain(monkeypatch, provider)

    result = search_pending_subtitle_candidates(in_memory_session, series, 1, 4, "en")

    assert len(result) == 1
    assert provider.search_calls == [
        {
            "season": 1,
            "episode": 4,
            "video_path": None,
            "imdb_id": None,
            "series_imdb_id": "tt1234567",
        }
    ]


def test_search_aggregates_and_scores_candidates(in_memory_session, monkeypatch):
    series = _series(in_memory_session)
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            ),
            SubtitleSearchResult(
                release_name="Ahsoka.S01E04.WEB.x264-GROUP", download_id="2", language="en"
            ),
        ],
    )
    _use_chain(monkeypatch, provider)

    result = search_pending_subtitle_candidates(in_memory_session, series, 1, 4, "en")

    assert [candidate.download_id for candidate in result] == ["2", "1"]
    assert result[0].score >= result[1].score


def test_search_returns_empty_list_for_an_empty_chain(in_memory_session, monkeypatch):
    series = _series(in_memory_session)
    _use_chain(monkeypatch)

    result = search_pending_subtitle_candidates(in_memory_session, series, 1, 4, "en")

    assert result == []
