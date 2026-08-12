import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.locate import resolve_media_file_owner
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.match_score import pick_best_match
from legendarr_backend.subtitle_acquisition.opensubtitles_hash import compute_opensubtitles_hash
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleProvider
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcquisitionResult:
    """Outcome of one `acquire_subtitle_for_media_file` run. `skipped_reason` is set
    (and `acquired_language` left `None`) for every expected, non-error outcome — no
    language profile, no provider configured, or nothing cleared the match cutoff.
    `None`/`None` (both fields unset) means a source-language subtitle already existed
    — a genuine no-op, not something worth a reason string. None of these are errors;
    they're common states the job logs and moves past instead of failing.
    """

    acquired_language: str | None = None
    skipped_reason: str | None = None


def acquire_subtitle_for_media_file(
    session: Session, media_file: MediaFile, video_path: Path
) -> AcquisitionResult:
    """Search and download a source-language subtitle for `media_file` when it has
    none yet (external or embedded), in its `LanguageProfile`'s source-language
    priority order, stopping at the first language a configured provider finds an
    above-cutoff match for.

    Movies get their search anchored on `Movie.imdb_id` — the precise, single-title
    lookup OpenSubtitles' API is built around. Series can't: a `MediaFile` doesn't
    carry its episode's season/episode number (only `Series`-level sync data exists
    today — see ROADMAP 0.6.0), so a series search is title-only and less precise;
    `pick_best_match`'s cutoff is what keeps a wrong episode's subtitle from being
    accepted. `SubtitleProviderConfig.use_hash` (OpenSubtitles' own `moviehash`,
    computed from `video_path` when reachable) applies to either.

    This never runs automatically from `translate_media_file` — that unification is
    0.11.0/0.12.0 roadmap work; this is a standalone, explicitly-triggered step (see
    `subtitle_acquisition/jobs.py`).
    """
    profile = resolve_media_file_profile(session, media_file)
    if profile is None:
        logger.info("acquisition skipped: media file %d has no language profile", media_file.id)
        return AcquisitionResult(skipped_reason="no_language_profile")
    assert media_file.id is not None

    if _has_source_language_subtitle(session, media_file, profile.source_language_list):
        return AcquisitionResult()

    chain = resolve_subtitle_provider_chain(session)
    if not chain:
        logger.info(
            "acquisition skipped: media file %d has no subtitle provider configured",
            media_file.id,
        )
        return AcquisitionResult(skipped_reason="no_provider_configured")

    owner = resolve_media_file_owner(session, media_file)
    # Guaranteed non-None here: `resolve_media_file_profile` above already resolved the
    # same owner to get this far, so this is a second read of a row known to exist, not
    # a real possible-None branch.
    assert owner is not None

    imdb_id = owner.imdb_id if isinstance(owner, Movie) else None
    moviehash = compute_opensubtitles_hash(video_path) if video_path.is_file() else None

    for language in profile.source_language_list:
        result = _search_and_download(chain, owner.title, language, imdb_id, moviehash, video_path)
        if result is None:
            continue
        output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}.srt")
        output_path.write_text(result, encoding="utf-8")
        scan_subtitles_for_media_file(session, media_file, video_path)
        return AcquisitionResult(acquired_language=language)

    logger.info(
        "acquisition failed: media file %d found no above-cutoff match in any source language",
        media_file.id,
    )
    return AcquisitionResult(skipped_reason="no_match_found")


def _has_source_language_subtitle(
    session: Session, media_file: MediaFile, source_languages: list[str]
) -> bool:
    existing_languages = set(
        session.exec(select(Subtitle.language).where(Subtitle.media_file_id == media_file.id)).all()
    )
    return any(language.lower() in existing_languages for language in source_languages)


def _search_and_download(
    chain: list[SubtitleProvider],
    title: str,
    language: str,
    imdb_id: str | None,
    moviehash: str | None,
    video_path: Path,
) -> str | None:
    for provider in chain:
        try:
            candidates = provider.search(title, language, imdb_id=imdb_id, moviehash=moviehash)
            best = pick_best_match(candidates, video_path.stem)
            if best is None:
                continue
            return provider.download(best)
        except Exception:
            logger.warning(
                "subtitle provider %r failed searching %r (%s), trying next",
                provider.name,
                title,
                language,
            )
    return None
