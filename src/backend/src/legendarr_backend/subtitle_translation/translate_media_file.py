import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, col, select

from legendarr_backend.language_profiles.models import LanguageProfile
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
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import (
    clear_translation_blacklist,
    is_translation_blacklisted,
)
from legendarr_backend.subtitle_discovery.clean_subtitle_text import clean_subtitle_lines
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
from legendarr_backend.subtitle_translation.translation_history import (
    record_translation_attempt,
    record_translation_failure,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranslationResult:
    """Outcome of one `translate_media_file` run.

    `skipped_reason` is set (and `translated_languages` left empty) whenever a
    precondition isn't met — no language profile, no subtitle (external or embedded) in a
    source language, no translation provider configured, or the picked source subtitle's
    file is missing from disk — or, for a manually-picked `source_subtitle_id`, that id not
    belonging to this media file. None of these are errors; they're expected, common states
    the job logs and moves past instead of failing.
    """

    translated_languages: list[str]
    skipped_reason: str | None = None


def translate_media_file(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    default_translation_provider: str | None = None,
    source_subtitle_id: int | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> TranslationResult:
    """Translate one `MediaFile` into every target language its `LanguageProfile` is
    still missing, from an already-discovered subtitle in one of its source languages.
    An external subtitle is preferred; an already-extracted embedded track is only used
    as the source when no external subtitle matches any configured source language
    (see `_pick_source_subtitle`).

    No acquisition fallback of its own: if no subtitle (external or embedded) exists yet in
    a source language, this is a no-op (`skipped_reason="no_source_subtitle"`) — triggering
    a `SubtitleProvider` search/download is orchestration, not translation, so it stays out
    of this function. `subtitle_translation.jobs.run_translation` is the caller that acts on
    that skip reason, cascading into `subtitle_acquisition.jobs.enqueue_acquisition` and
    retrying translation once acquisition finds something (ROADMAP.md 0.12.0's unified
    ordered strategy). A manually-picked `source_subtitle_id` that isn't found has no such
    fallback — `skipped_reason="source_subtitle_not_found"` instead, left as-is since that's
    an explicit user override, not a missing-subtitle case acquisition could resolve.

    `default_translation_provider` is the Settings-configured default (see
    `resolve_provider_chain`); passed through unchanged, `None` means no preference.

    `source_subtitle_id`, when given, bypasses `_pick_source_subtitle` entirely and uses that
    `Subtitle` row as the source instead — manual override for ROADMAP.md 0.11.0's "pick which
    one to translate". Unrestricted by `profile.source_language_list`: any subtitle already
    discovered for this media file, external or embedded, in any language, is a valid manual
    source. Everything past the source pick (missing-target check, provider chain, writing
    output) behaves identically either way.

    `on_progress`, when given, is called once per target language — `(current, total,
    target_language)`, 1-indexed — right before that language's translation attempt starts.
    ROADMAP.md 0.20.0's "Live progress": `subtitle_translation.jobs.run_translation` is the
    only caller that passes one, wiring it into `scheduling.running_tasks.report_progress`.
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
            .order_by(col(Subtitle.scanned_at))
        )
    }

    if source_subtitle_id is None:
        source = _pick_source_subtitle(profile, external_subtitles, embedded_subtitles)
        if source is None:
            logger.info(
                "translation skipped: media file %d has no subtitle in a source language",
                media_file.id,
            )
            return TranslationResult(translated_languages=[], skipped_reason="no_source_subtitle")
    else:
        source = session.get(Subtitle, source_subtitle_id)
        if source is None or source.media_file_id != media_file.id:
            logger.info(
                "translation skipped: media file %d's requested source subtitle %s not found",
                media_file.id,
                source_subtitle_id,
            )
            return TranslationResult(
                translated_languages=[], skipped_reason="source_subtitle_not_found"
            )

    # An already-extracted embedded track also satisfies a target language on its own,
    # even when a *different* embedded track was picked as the source above.
    embedded_languages = set(embedded_subtitles)
    missing_targets = _missing_targets(profile, external_subtitles, embedded_languages, source)
    if source_subtitle_id is None:
        # Automatic call only — a blacklisted target stays "missing" rather than being
        # silently regenerated by the periodic translation fan-out; an explicit manual
        # retry (`source_subtitle_id` given) is exempt and clears the block below once it
        # actually retranslates the language.
        missing_targets = [
            language
            for language in missing_targets
            if not is_translation_blacklisted(session, media_file.id, language)
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
    # ROADMAP 0.13.0's text cleanup pass — only the in-memory copy fed to translation is
    # cleaned, the source `.srt` on disk is never rewritten.
    lines = clean_subtitle_lines(lines)

    translated_languages = []
    provider_by_target_language: dict[str, str] = {}
    total_targets = len(missing_targets)
    for current_target, target_language in enumerate(missing_targets, start=1):
        if on_progress is not None:
            on_progress(current_target, total_targets, target_language)
        result = _translate_with_fallback(
            session, chain, lines, source.language, target_language, media_file.id
        )
        if result is None:
            continue
        translated_lines, provider_name = result
        # Lowercased to match the suffix `_guess_language_from_filename` will read back
        # on the next scan — otherwise a mixed-case profile code (e.g. `pt-BR`) would
        # never match its own output and get retranslated every run.
        output_path = video_path.with_name(f"{video_path.stem}.{target_language.lower()}.srt")
        output_path.write_text(compose_srt(translated_lines), encoding="utf-8")
        translated_languages.append(target_language)
        provider_by_target_language[target_language] = provider_name

    if translated_languages:
        scan_subtitles_for_media_file(session, media_file, video_path)
        _stamp_translated_from_hash(session, media_file, translated_languages, source.content_hash)
        _record_translation_attempts(
            session, media_file, translated_languages, source.language, provider_by_target_language
        )
        if source_subtitle_id is not None:
            for target_language in translated_languages:
                clear_translation_blacklist(session, media_file.id, target_language)

    return TranslationResult(translated_languages=translated_languages)


def _missing_targets(
    profile: LanguageProfile,
    external_subtitles: dict[str, Subtitle],
    embedded_languages: set[str],
    source: Subtitle,
) -> list[str]:
    """Target languages that still need a translation run.

    A target already covered by an embedded track is always satisfied — embedded tracks
    are never produced by translation, so there's no staleness to check. A target already
    covered by an external subtitle is satisfied unless it was itself produced by a
    previous translation (`translated_from_hash` set) whose source has since changed
    (`translated_from_hash != source.content_hash`) — a subtitle we never translated (a
    user-provided or acquired one already in the target language) is left alone either
    way, matching the pre-existing behavior.
    """
    missing = []
    for language in profile.target_language_list:
        existing = external_subtitles.get(language.lower())
        if existing is not None:
            if existing.translated_from_hash is not None and (
                existing.translated_from_hash != source.content_hash
            ):
                missing.append(language)
            continue
        if normalize_language_code(language) not in embedded_languages:
            missing.append(language)
    return missing


def _stamp_translated_from_hash(
    session: Session,
    media_file: MediaFile,
    translated_languages: list[str],
    source_content_hash: str,
) -> None:
    """Record the source hash each just-translated target was produced from, on the
    `Subtitle` row `scan_subtitles_for_media_file` just wrote/updated for it — read back
    on the next run by `_missing_targets` to tell an unchanged source from a stale one.
    """
    for target_language in translated_languages:
        row = session.exec(
            select(Subtitle).where(
                Subtitle.media_file_id == media_file.id,
                Subtitle.origin == SubtitleOrigin.EXTERNAL,
                Subtitle.language == target_language.lower(),
            )
        ).first()
        if row is not None:
            row.translated_from_hash = source_content_hash
            session.add(row)


def _record_translation_attempts(
    session: Session,
    media_file: MediaFile,
    translated_languages: list[str],
    source_language: str,
    provider_by_target_language: dict[str, str],
) -> None:
    """Append one `TranslationAttempt` per just-translated target — ROADMAP.md 0.20.0's
    Statistics view data source. Same row lookup as `_stamp_translated_from_hash` (the
    `Subtitle` row `scan_subtitles_for_media_file` just wrote/updated), since an audit
    trail row needs the target's own `subtitle_id`, not the source's.
    """
    translated_at = datetime.now(UTC)
    for target_language in translated_languages:
        row = session.exec(
            select(Subtitle).where(
                Subtitle.media_file_id == media_file.id,
                Subtitle.origin == SubtitleOrigin.EXTERNAL,
                Subtitle.language == target_language.lower(),
            )
        ).first()
        if row is not None and row.id is not None:
            record_translation_attempt(
                session,
                row.id,
                provider=provider_by_target_language[target_language],
                source_language=source_language,
                target_language=target_language,
                translated_at=translated_at,
            )


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
    session: Session,
    chain: list[TranslationProvider],
    lines: list[SubtitleLine],
    source_language: str,
    target_language: str,
    media_file_id: int,
) -> tuple[list[SubtitleLine], str] | None:
    last_error: Exception | None = None
    last_provider_name: str | None = None
    for provider in chain:
        if is_open(BreakerCategory.TRANSLATION, provider.name):
            logger.info(
                "translation provider %r circuit open, skipping for media file %d (%s -> %s)",
                provider.name,
                media_file_id,
                source_language,
                target_language,
            )
            continue
        try:
            translated = translate_subtitle(lines, provider, source_language, target_language)
            record_success(BreakerCategory.TRANSLATION, provider.name)
            return translated, provider.name
        except Exception as exc:
            record_failure(BreakerCategory.TRANSLATION, provider.name)
            last_error = exc
            last_provider_name = provider.name
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
    if last_error is not None:
        record_translation_failure(
            session,
            media_file_id,
            source_language=source_language,
            target_language=target_language,
            error_message=f"{last_provider_name}: {last_error}",
            failed_at=datetime.now(UTC),
        )
    return None
