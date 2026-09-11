import logging
import threading
import time
from collections.abc import Callable, Sequence, Set
from dataclasses import dataclass
from pathlib import Path

from legendarr_backend.scheduling.circuit_breaker import (
    BreakerCategory,
    is_open,
    record_failure,
    record_success,
)
from legendarr_backend.scheduling.provider_concurrency import (
    ConcurrencyCategory,
    limit_concurrency,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.episode_identity import (
    passes_episode_identity,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    score_candidate,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_filters import (
    passes_release_name_filters,
)
from legendarr_backend.subtitle_acquisition.providers.base import (
    SubtitleProvider,
    SubtitleSearchResult,
)

logger = logging.getLogger(__name__)

# How long to wait for one provider's `search()` before giving up on it. Generous
# against a slow-but-working provider — `http_client.ProviderHttpClient` already bounds
# every HTTP call at 10s and retries twice — and short enough that a provider blocked on
# something no HTTP timeout covers (a hash read off a stalled network mount, see
# `providers/napiprojekt_hash.py`) can't hold an acquisition worker forever.
DEFAULT_PROVIDER_SEARCH_TIMEOUT_SECONDS = 120.0

type _ProviderSearch = tuple[SubtitleProvider, list[SubtitleSearchResult], Exception | None]


@dataclass(frozen=True)
class SubtitleCandidate:
    """One provider search result, tagged with which provider found it and how close
    a textual match it is — everything a manual "pick one" UI needs to display and,
    on download, to re-locate the same provider/result. Re-exported from
    `search_media_file_subtitle.py` (its original home, and where every other importer
    still reaches it) to keep this module import-cycle-free from the callers that
    depend on it.
    """

    provider: str
    release_name: str
    download_id: str
    language: str
    page_link: str | None
    # Unused by `download_subtitle_candidate` — only meaningful for the search
    # results list, so a caller reconstructing a candidate from a download request
    # (which doesn't carry a score) can leave it at the default.
    score: float = 0.0
    # Display-only, same as `SubtitleSearchResult.uploader` it's copied from — `None`
    # for every provider but OpenSubtitles, which doesn't set it either for an
    # anonymous upload.
    uploader: str | None = None


@dataclass(frozen=True)
class ScoredCandidate:
    """One provider result, already filtered and scored. `result` is the raw
    `SubtitleSearchResult` (`hash_matched`/`hearing_impaired` intact) a caller needs to
    `provider.download()` it and re-evaluate it for the audit trail; `candidate` is the
    flattened `SubtitleCandidate` — the same shape a manual-search caller just wants to
    list/display.
    """

    provider: SubtitleProvider
    result: SubtitleSearchResult
    candidate: SubtitleCandidate


def search_providers_concurrently(
    chain: list[SubtitleProvider],
    title: str,
    language: str,
    *,
    imdb_id: str | None,
    moviehash: str | None,
    season: int | None,
    episode: int | None,
    video_path: Path | None,
    tvdb_id: int | None,
    series_imdb_id: str | None,
    reference_filename: str,
    hearing_impaired_preference: bool | None = None,
    blacklisted: Set[tuple[str, str]] = frozenset(),
    must_contain: Sequence[str] = (),
    must_not_contain: Sequence[str] = (),
    check_episode_identity: bool = True,
    on_dispatch: Callable[[SubtitleProvider], None] | None = None,
    timeout_seconds: float = DEFAULT_PROVIDER_SEARCH_TIMEOUT_SECONDS,
) -> tuple[list[ScoredCandidate], Exception | None, str | None]:
    """Search every provider in `chain` concurrently (skipping one with an open
    circuit, same as a sequential loop would), filter and score everything that comes
    back, and return it all sorted best-first — the "compile by best score across
    providers" every caller needs, whether it wants the whole list (manual search) or
    just the winner (automatic acquisition, which walks the sorted list itself trying
    to download each one in turn).

    `check_episode_identity` is on by default (`_search_and_download` and
    `search_media_file_subtitle_candidates` both need it); `search_pending_subtitle_candidates`
    is the one caller that turns it off — same as it not applying that gate today.

    `on_dispatch`, when given, is called once per eligible provider — synchronously,
    in `chain` order, before any of them are actually searched — so a caller driving
    `on_progress`/live task status can report "searching via provider N" deterministically
    instead of racing the concurrent searches themselves.

    Also returns the last-in-`chain`-order provider that raised, and the exception it
    raised (`None`, `None` when every eligible provider either succeeded or was skipped)
    — the same "last error wins" bookkeeping a sequential loop's `last_error`/
    `last_provider_name` locals would end up with, for a caller that wants to record why
    nothing was found.

    A provider that hasn't answered within `timeout_seconds` is abandoned and reported
    as a `TimeoutError` of its own — see `_search_all` for why waiting on it instead
    would wedge the calling worker permanently.
    """
    eligible: list[SubtitleProvider] = []
    for provider in chain:
        if is_open(BreakerCategory.ACQUISITION, provider.name):
            logger.info(
                "subtitle provider %r circuit open, skipping search for %r (%s)",
                provider.name,
                title,
                language,
            )
            continue
        eligible.append(provider)
        if on_dispatch is not None:
            on_dispatch(provider)

    def _search_one(provider: SubtitleProvider) -> _ProviderSearch:
        try:
            with limit_concurrency(ConcurrencyCategory.ACQUISITION, provider.name):
                results = provider.search(
                    title,
                    language,
                    imdb_id=imdb_id,
                    moviehash=moviehash,
                    season=season,
                    episode=episode,
                    video_path=video_path,
                    tvdb_id=tvdb_id,
                    series_imdb_id=series_imdb_id,
                )
            record_success(BreakerCategory.ACQUISITION, provider.name)
            return provider, results, None
        except Exception as exc:
            record_failure(BreakerCategory.ACQUISITION, provider.name)
            return provider, [], exc

    searched = _search_all(eligible, _search_one, timeout_seconds)

    must_contain_list = list(must_contain)
    must_not_contain_list = list(must_not_contain)
    scored: list[ScoredCandidate] = []
    last_error: Exception | None = None
    last_provider_name: str | None = None
    for provider, results, exc in searched:
        if exc is not None:
            last_error = exc
            last_provider_name = provider.name
            logger.warning(
                "subtitle provider %r failed searching %r (%s), trying next",
                provider.name,
                title,
                language,
            )
            continue
        for result in results:
            if (provider.name, result.download_id) in blacklisted:
                continue
            if check_episode_identity and not passes_episode_identity(result, season, episode):
                continue
            if not passes_release_name_filters(
                result.release_name, must_contain_list, must_not_contain_list
            ):
                continue
            candidate = SubtitleCandidate(
                provider=provider.name,
                release_name=result.release_name,
                download_id=result.download_id,
                language=result.language,
                page_link=result.page_link,
                score=score_candidate(result, reference_filename, hearing_impaired_preference),
                uploader=result.uploader,
            )
            scored.append(ScoredCandidate(provider=provider, result=result, candidate=candidate))

    scored.sort(key=lambda scored_candidate: scored_candidate.candidate.score, reverse=True)
    return scored, last_error, last_provider_name


def _search_all(
    eligible: list[SubtitleProvider],
    search_one: Callable[[SubtitleProvider], _ProviderSearch],
    timeout_seconds: float,
) -> list[_ProviderSearch]:
    """Run `search_one` for every provider in `eligible`, concurrently, and stop waiting
    once `timeout_seconds` have passed — returning one entry per provider, in `eligible`
    order, with whatever hasn't come back by then reported as a timeout.

    A `ThreadPoolExecutor` is the obvious fit and is deliberately not used: its
    `__exit__` is a `shutdown(wait=True)`, so a single provider blocked on something no
    HTTP timeout covers would hold this worker forever, and its non-daemon pool threads
    would block interpreter shutdown on top of that. Same `Thread(daemon=True)` plus one
    bounded `join()` shape as `opensubtitles_hash.compute_opensubtitles_hash` and
    `audio_transcription.transcribe_audio` — the stuck thread is abandoned, never waited
    on a second time.

    A timed-out provider is recorded as a circuit-breaker failure like any other
    failure, so a provider that keeps not answering opens its circuit and stops being
    searched at all instead of costing `timeout_seconds` on every media file.
    """
    results: dict[int, _ProviderSearch] = {}

    def _target(index: int, provider: SubtitleProvider) -> None:
        results[index] = search_one(provider)

    threads = [
        threading.Thread(target=_target, args=(index, provider), daemon=True)
        for index, provider in enumerate(eligible)
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout_seconds
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))

    searched: list[_ProviderSearch] = []
    for index, provider in enumerate(eligible):
        finished = results.get(index)
        if finished is not None:
            searched.append(finished)
            continue
        logger.warning(
            "subtitle provider %r did not answer within %.0fs, abandoning its search",
            provider.name,
            timeout_seconds,
        )
        record_failure(BreakerCategory.ACQUISITION, provider.name)
        searched.append(
            (
                provider,
                [],
                TimeoutError(f"{provider.name} search timed out after {timeout_seconds:.0f}s"),
            )
        )
    return searched
