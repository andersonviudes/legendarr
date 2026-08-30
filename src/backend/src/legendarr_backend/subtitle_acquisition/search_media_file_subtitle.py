import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.scheduling.circuit_breaker import (
    BreakerCategory,
    is_open,
    record_failure,
    record_success,
)
from legendarr_backend.subtitle_acquisition.blacklist.manage_subtitle_blacklist import (
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.episode_identity import (
    passes_episode_identity,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    score_candidate,
)
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubtitleCandidate:
    """One provider search result, tagged with which provider found it and how close
    a textual match it is — everything a manual "pick one" UI needs to display and,
    on download, to re-locate the same provider/result.
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


def search_media_file_subtitle_candidates(
    session: Session, media_file: MediaFile, video_path: Path, language: str
) -> list[SubtitleCandidate]:
    """Search every configured provider for `language` and return every result found,
    best match first — unlike `acquire_subtitle_for_media_file`'s automatic path, this
    never stops at the first above-cutoff match: a manual search is for a user to
    browse and choose from, so every provider is tried and every candidate is kept,
    regardless of score.
    """
    assert media_file.id is not None
    context = resolve_subtitle_search_context(session, media_file, video_path)
    profile = resolve_media_file_profile(session, media_file)
    hearing_impaired_preference = profile.hearing_impaired if profile is not None else None
    chain = resolve_subtitle_provider_chain(session)
    blacklisted = list_blacklisted_download_ids(session, media_file.id, language)
    candidates: list[SubtitleCandidate] = []
    try:
        for provider in chain:
            if is_open(BreakerCategory.ACQUISITION, provider.name):
                logger.info(
                    "subtitle provider %r circuit open, skipping search for %r (%s)",
                    provider.name,
                    context.title,
                    language,
                )
                continue
            try:
                results = provider.search(
                    context.title,
                    language,
                    imdb_id=context.imdb_id,
                    moviehash=context.moviehash,
                    season=context.season_number,
                    episode=context.episode_number,
                    video_path=video_path,
                    tvdb_id=context.tvdb_id,
                    series_imdb_id=context.series_imdb_id,
                )
                record_success(BreakerCategory.ACQUISITION, provider.name)
            except Exception:
                record_failure(BreakerCategory.ACQUISITION, provider.name)
                logger.warning(
                    "subtitle provider %r failed searching %r (%s), trying next",
                    provider.name,
                    context.title,
                    language,
                )
                continue
            candidates.extend(
                SubtitleCandidate(
                    provider=provider.name,
                    release_name=result.release_name,
                    download_id=result.download_id,
                    language=result.language,
                    page_link=result.page_link,
                    score=score_candidate(result, video_path.stem, hearing_impaired_preference),
                    uploader=result.uploader,
                )
                for result in results
                if (provider.name, result.download_id) not in blacklisted
                and passes_episode_identity(result, context.season_number, context.episode_number)
            )
    finally:
        # Same close-what-needs-closing shape as `acquire_subtitle_for_media_file` —
        # a provider that holds a session for its whole lifetime (Addic7ed) needs it.
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates
