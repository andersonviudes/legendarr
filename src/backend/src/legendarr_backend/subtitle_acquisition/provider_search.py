import logging
from collections.abc import Callable, Sequence, Set
from concurrent.futures import ThreadPoolExecutor
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

    def _search_one(
        provider: SubtitleProvider,
    ) -> tuple[SubtitleProvider, list[SubtitleSearchResult], Exception | None]:
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

    searched: list[tuple[SubtitleProvider, list[SubtitleSearchResult], Exception | None]]
    if eligible:
        with ThreadPoolExecutor(max_workers=len(eligible)) as executor:
            searched = list(executor.map(_search_one, eligible))
    else:
        searched = []

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
