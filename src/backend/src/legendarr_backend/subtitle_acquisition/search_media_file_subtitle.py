from pathlib import Path

from sqlmodel import Session

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.blacklist.manage_subtitle_blacklist import (
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.provider_search import (
    SubtitleCandidate,
    search_providers_concurrently,
)
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context

# `SubtitleCandidate` now lives in `provider_search.py` (to keep that module free of an
# import cycle back into this one) but is imported here too, since `media_library/router.py`
# and other existing importers still reach it through this module.


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
    try:
        scored, _, _ = search_providers_concurrently(
            chain,
            context.title,
            language,
            imdb_id=context.imdb_id,
            moviehash=context.moviehash,
            season=context.season_number,
            episode=context.episode_number,
            video_path=video_path,
            tvdb_id=context.tvdb_id,
            series_imdb_id=context.series_imdb_id,
            reference_filename=video_path.stem,
            hearing_impaired_preference=hearing_impaired_preference,
            blacklisted=blacklisted,
        )
    finally:
        # Same close-what-needs-closing shape as `acquire_subtitle_for_media_file` —
        # a provider that holds a session for its whole lifetime (Addic7ed) needs it.
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    return [scored_candidate.candidate for scored_candidate in scored]
