import logging
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, col, select

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.language_codes import normalize_language_code
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
    precondition isn't met — no language profile, no subtitle (external or embedded) in a
    source language, no translation provider configured, or the picked source subtitle's
    file is missing from disk. None of these are errors; they're expected, common states
    the job logs and moves past instead of failing.
    """

    translated_languages: list[str]
    skipped_reason: str | None = None


def translate_media_file(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    default_translation_provider: str | None = None,
) -> TranslationResult:
    """Translate one `MediaFile` into every target language its `LanguageProfile` is
    still missing, from an already-discovered subtitle in one of its source languages.
    An external subtitle is preferred; an already-extracted embedded track is only used
    as the source when no external subtitle matches any configured source language
    (see `_pick_source_subtitle`).

    No acquisition fallback: if no subtitle (external or embedded) exists yet in a source
    language, this is a no-op — that needs real `SubtitleProvider` search/download,
    still 0.11.0/0.12.0 work.

    `default_translation_provider` is the Settings-configured default (see
    `resolve_provider_chain`); passed through unchanged, `None` means no preference.
    """
    profile = resolve_media_file_profile(session, media_file)
    if profile is None:
        logger.info("translation skipped: media file %d has no language profile", media_file.id)
        return TranslationResult(translated_languages=[], skipped_reason="no_language_profile")
    assert media_file.id is not None

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
            .order_by(col(Subtitle.scanned_at))
        )
    }

    # Keyed by the already-normalized language `scan_video_subtitles` persists for an
    # embedded row (`language_codes.normalize_language_code`, e.g. ffprobe's "por" ->
    # "pt") — region-blind, same as the target-satisfaction check below, since ffprobe has
    # no way to tell e.g. Brazilian from European Portuguese. Same oldest-first ordering as
    # `external_subtitles`.
    embedded_subtitles = {
        subtitle.language: subtitle
        for subtitle in session.exec(
            select(Subtitle)
            .where(
                Subtitle.media_file_id == media_file.id,
                Subtitle.origin == SubtitleOrigin.EMBEDDED,
            )
            .order_by(Subtitle.scanned_at)
        )
    }

    source = _pick_source_subtitle(profile, external_subtitles, embedded_subtitles)
    if source is None:
        logger.info(
            "translation skipped: media file %d has no subtitle in a source language",
            media_file.id,
        )
        return TranslationResult(translated_languages=[], skipped_reason="no_source_subtitle")

    # An already-extracted embedded track also satisfies a target language on its own,
    # even when a *different* embedded track was picked as the source above.
    embedded_languages = set(embedded_subtitles)
    missing_targets = [
        language
        for language in profile.target_language_list
        if language.lower() not in external_subtitles
        and normalize_language_code(language) not in embedded_languages
    ]
    if not missing_targets:
        return TranslationResult(translated_languages=[])

    chain = resolve_provider_chain(session, default_translation_provider)
    if not chain:
        logger.info(
            "translation skipped: media file %d has no translation provider configured",
            media_file.id,
        )
        return TranslationResult(translated_languages=[], skipped_reason="no_provider_configured")

    source_path = video_path.parent / Path(source.relative_path).name
    if not source_path.is_file():
        logger.warning(
            "translation skipped: media file %d's source subtitle row points to a missing file %s",
            media_file.id,
            source_path,
        )
        return TranslationResult(
            translated_languages=[], skipped_reason="source_subtitle_missing_on_disk"
        )
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


def _pick_source_subtitle(
    profile: LanguageProfile,
    external_subtitles: dict[str, Subtitle],
    embedded_subtitles: dict[str, Subtitle],
) -> Subtitle | None:
    """Pick the subtitle to translate from, in `profile.source_language_list` priority
    order. External is preferred globally over embedded: every source language is tried
    against `external_subtitles` first, and only once none of them matched at all does a
    second pass fall back to `embedded_subtitles` — an embedded track never wins over an
    external one just because it's in a higher-priority source language.
    """
    for language in profile.source_language_list:
        subtitle = external_subtitles.get(language.lower())
        if subtitle is not None:
            return subtitle
    for language in profile.source_language_list:
        subtitle = embedded_subtitles.get(normalize_language_code(language))
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
