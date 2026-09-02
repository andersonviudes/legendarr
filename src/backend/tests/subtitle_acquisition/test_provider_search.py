from legendarr_backend.scheduling.circuit_breaker import (
    FAILURE_THRESHOLD,
    BreakerCategory,
    is_open,
    record_failure,
)
from legendarr_backend.subtitle_acquisition.provider_search import search_providers_concurrently
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult


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
        self.search_calls.append({"title": title, "language": language})
        return self.results

    def download(self, result):
        raise NotImplementedError


class _FailingProvider:
    def __init__(self, name: str = "failing"):
        self.name = name
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
        self.search_calls.append({"title": title, "language": language})
        raise RuntimeError("boom")

    def download(self, result):
        raise NotImplementedError


def _search(chain, **overrides):
    kwargs = {
        "imdb_id": None,
        "moviehash": None,
        "season": None,
        "episode": None,
        "video_path": None,
        "tvdb_id": None,
        "series_imdb_id": None,
        "reference_filename": "Foo",
    }
    kwargs.update(overrides)
    return search_providers_concurrently(chain, "Foo", "en", **kwargs)


def test_aggregates_candidates_from_every_provider():
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

    scored, last_error, last_provider_name = _search([provider_a, provider_b])

    assert {sc.provider.name for sc in scored} == {"provider-a", "provider-b"}
    assert {sc.candidate.download_id for sc in scored} == {"1", "2"}
    assert last_error is None
    assert last_provider_name is None


def test_sorts_candidates_by_score_descending():
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            ),
            SubtitleSearchResult(release_name="Foo", download_id="2", language="en"),
        ],
    )

    scored, _, _ = _search([provider])

    assert [sc.candidate.download_id for sc in scored] == ["2", "1"]
    assert scored[0].candidate.score >= scored[1].candidate.score


def test_a_failing_provider_does_not_block_others_and_is_surfaced_as_the_last_error():
    working = _FakeProvider(
        "working",
        results=[SubtitleSearchResult(release_name="Foo", download_id="1", language="en")],
    )
    failing = _FailingProvider()

    scored, last_error, last_provider_name = _search([working, failing])

    assert [sc.candidate.provider for sc in scored] == ["working"]
    assert isinstance(last_error, RuntimeError)
    assert last_provider_name == "failing"


def test_skips_a_provider_with_an_open_circuit(isolated_circuit_breakers):
    failing = _FailingProvider()
    working = _FakeProvider(
        "working",
        results=[SubtitleSearchResult(release_name="Foo", download_id="1", language="en")],
    )
    for _ in range(FAILURE_THRESHOLD):
        record_failure(BreakerCategory.ACQUISITION, failing.name)

    scored, _, _ = _search([failing, working])

    assert [sc.candidate.provider for sc in scored] == ["working"]
    assert failing.search_calls == []


def test_records_circuit_breaker_success_and_failure(isolated_circuit_breakers):
    working = _FakeProvider("working")
    failing = _FailingProvider()

    _search([working, failing])

    assert is_open(BreakerCategory.ACQUISITION, "working") is False
    for _ in range(FAILURE_THRESHOLD - 1):
        _search([failing])
    assert is_open(BreakerCategory.ACQUISITION, "failing") is True


def test_filters_out_a_blacklisted_download_id():
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(release_name="Foo", download_id="1", language="en"),
            SubtitleSearchResult(release_name="Foo", download_id="2", language="en"),
        ],
    )

    scored, _, _ = _search([provider], blacklisted={("provider", "1")})

    assert [sc.candidate.download_id for sc in scored] == ["2"]


def test_applies_must_contain_and_must_not_contain_filters():
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(release_name="Foo.HI", download_id="1", language="en"),
            SubtitleSearchResult(release_name="Foo.WEB-DL", download_id="2", language="en"),
        ],
    )

    scored, _, _ = _search([provider], must_contain=["web-dl"], must_not_contain=["hi"])

    assert [sc.candidate.download_id for sc in scored] == ["2"]


def test_excludes_a_wrong_episode_candidate_by_default():
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

    scored, _, _ = _search([provider], season=1, episode=2)

    assert [sc.candidate.download_id for sc in scored] == ["right"]


def test_check_episode_identity_false_keeps_a_wrong_episode_candidate():
    provider = _FakeProvider(
        "provider",
        results=[
            SubtitleSearchResult(
                release_name="Foo.S01E03.WEB-DL", download_id="wrong", language="en"
            )
        ],
    )

    scored, _, _ = _search([provider], season=1, episode=2, check_episode_identity=False)

    assert [sc.candidate.download_id for sc in scored] == ["wrong"]


def test_on_dispatch_called_once_per_eligible_provider_in_chain_order_before_results(
    isolated_circuit_breakers,
):
    open_circuit = _FailingProvider("open-circuit")
    for _ in range(FAILURE_THRESHOLD):
        record_failure(BreakerCategory.ACQUISITION, open_circuit.name)
    provider_a = _FakeProvider("provider-a")
    provider_b = _FakeProvider("provider-b")
    dispatched = []

    _search([open_circuit, provider_a, provider_b], on_dispatch=lambda p: dispatched.append(p.name))

    assert dispatched == ["provider-a", "provider-b"]
