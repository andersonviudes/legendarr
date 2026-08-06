import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_effective_profile,
)
from legendarr_backend.media_library.locate import resolve_media_file_owner
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_discovery.subtitle_format import (
    SubtitleLine,
    compose_srt,
    parse_srt,
)
from legendarr_backend.subtitle_translation.provider_chain import resolve_provider_chain
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider
from legendarr_backend.subtitle_translation.translate_subtitle import translate_subtitle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranslationResult:
    """Outcome of one `translate_media_file` run.

    `skipped_reason` is set (and `translated_languages` left empty) whenever a
    precondition isn't met — no language profile, no external subtitle in a source
    language, or no translation provider configured. None of these are errors; they're
    expected, common states the job logs and moves past instead of failing.
    """

    translated_languages: list[str]
    skipped_reason: str | None = None


def translate_media_file(
    session: Session, media_file: MediaFile, video_path: Path
) -> TranslationResult:
    """Translate one `MediaFile` into every target language its `LanguageProfile` is
    still missing, from an already-discovered external subtitle in one of its source
    languages.

    No acquisition fallback: if no external subtitle exists yet in a source language,
    this is a no-op — that lands with real `SubtitleProvider` search/download at 0.6.0+.
    """
    profile = _resolve_language_profile(session, media_file)
    if profile is None:
        logger.info("translation skipped: media file %d has no language profile", media_file.id)
        return TranslationResult(translated_languages=[], skipped_reason="no_language_profile")

    # Keyed by the lowercase language `scan_video_subtitles._guess_language_from_filename`
    # actually persists, ordered oldest-first so a duplicate language keeps the most
    # recently scanned row.
    external_subtitles = {
        subtitle.language: subtitle
        for subtitle in session.exec(
            select(Subtitle)
            .where(
                Subtitle.media_file_id == media_file.id,
                Subtitle.origin == SubtitleOrigin.EXTERNAL,
            )
            .order_by(Subtitle.scanned_at)
        )
    }

    source = _pick_source_subtitle(profile, external_subtitles)
    if source is None:
        logger.info(
            "translation skipped: media file %d has no external subtitle in a source language",
            media_file.id,
        )
        return TranslationResult(translated_languages=[], skipped_reason="no_source_subtitle")

    missing_targets = [
        language
        for language in profile.target_language_list
        if language.lower() not in external_subtitles
    ]
    if not missing_targets:
        return TranslationResult(translated_languages=[])

    chain = resolve_provider_chain(session)
    if not chain:
        logger.info(
            "translation skipped: media file %d has no translation provider configured",
            media_file.id,
        )
        return TranslationResult(translated_languages=[], skipped_reason="no_provider_configured")

    source_path = video_path.parent / Path(source.relative_path).name
    lines = parse_srt(source_path.read_text(encoding="utf-8"))

    translated_languages = []
    for target_language in missing_targets:
        translated = _translate_with_fallback(
            chain, lines, source.language, target_language, media_file.id
        )
        if translated is None:
            continue
        # Lowercased to match the suffix `_guess_language_from_filename` will read back
        # on the next scan — otherwise a mixed-case profile code (e.g. `pt-BR`) would
        # never match its own output and get retranslated every run.
        output_path = video_path.with_name(f"{video_path.stem}.{target_language.lower()}.srt")
        output_path.write_text(compose_srt(translated), encoding="utf-8")
        translated_languages.append(target_language)

    if translated_languages:
        scan_subtitles_for_media_file(session, media_file, video_path)

    return TranslationResult(translated_languages=translated_languages)


def _resolve_language_profile(session: Session, media_file: MediaFile) -> LanguageProfile | None:
    item = resolve_media_file_owner(session, media_file)
    if item is None:
        return None
    return resolve_effective_profile(session, item)


def _pick_source_subtitle(
    profile: LanguageProfile, external_subtitles: dict[str, Subtitle]
) -> Subtitle | None:
    for language in profile.source_language_list:
        subtitle = external_subtitles.get(language.lower())
        if subtitle is not None:
            return subtitle
    return None


def _translate_with_fallback(
    chain: list[TranslationProvider],
    lines: list[SubtitleLine],
    source_language: str,
    target_language: str,
    media_file_id: int,
) -> list[SubtitleLine] | None:
    for provider in chain:
        try:
            return translate_subtitle(lines, provider, source_language, target_language)
        except Exception:
            logger.warning(
                "translation provider %r failed for media file %d (%s -> %s), trying next",
                provider.name,
                media_file_id,
                source_language,
                target_language,
            )
    logger.error(
        "translation failed for media file %d (%s -> %s): every configured provider failed",
        media_file_id,
        source_language,
        target_language,
    )
    return None
