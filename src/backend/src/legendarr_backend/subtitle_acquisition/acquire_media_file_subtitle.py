import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

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
from legendarr_backend.subtitle_acquisition.audio_transcription.probe_embedded_audio import (
    EmbeddedAudioTrack,
    extract_audio_track,
    probe_embedded_audio_tracks,
)
from legendarr_backend.subtitle_acquisition.audio_transcription.transcribe_audio import (
    transcribe_audio_track,
)
from legendarr_backend.subtitle_acquisition.audit_trail import record_acquisition_failure
from legendarr_backend.subtitle_acquisition.blacklist.manage_subtitle_blacklist import (
    list_blacklisted_download_ids,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    CandidateEvaluation,
    evaluate_candidate,
    pick_best_match,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.quality_gate import (
    passes_quality_gate,
)
from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_filters import (
    passes_release_name_filters,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleProvider
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context
from legendarr_backend.subtitle_discovery.language_codes import normalize_language_code
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
)
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)

# Default speech-to-text model size/timeout/model directory, mirroring
# `Settings.speech_to_text_model_size`/`speech_to_text_timeout_seconds`/
# `speech_to_text_model_dir` — production always passes the configured values explicitly
# (see `subtitle_acquisition/jobs.py`), same posture as
# `subtitle_discovery.probe_embedded_subtitles.DEFAULT_PROBE_TIMEOUT_SECONDS`.
DEFAULT_SPEECH_TO_TEXT_MODEL_SIZE = "base"
DEFAULT_SPEECH_TO_TEXT_TIMEOUT_SECONDS = 1800.0
DEFAULT_SPEECH_TO_TEXT_MODEL_DIR = Path("./data/whisper_models")


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


@dataclass(frozen=True)
class _AcquiredCandidate:
    """The winning candidate `_search_and_download` found, plus everything
    `record_acquired_subtitle` needs to save its provenance for a later upgrade check."""

    content: str
    provider: str
    release_name: str
    download_id: str
    evaluation: CandidateEvaluation


def acquire_subtitle_for_media_file(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    *,
    speech_to_text_model_size: str = DEFAULT_SPEECH_TO_TEXT_MODEL_SIZE,
    speech_to_text_timeout_seconds: float = DEFAULT_SPEECH_TO_TEXT_TIMEOUT_SECONDS,
    speech_to_text_model_dir: Path = DEFAULT_SPEECH_TO_TEXT_MODEL_DIR,
    on_progress: Callable[[int, int, str, str | None], None] | None = None,
) -> AcquisitionResult:
    """Search and download a source-language subtitle for `media_file` when it has
    none yet (external or embedded), in its `LanguageProfile`'s source-language
    priority order, stopping at the first language a configured provider finds an
    above-cutoff match for. Every candidate is first filtered against the profile's
    `must_contain_terms`/`must_not_contain_terms` (`release_filters.py`) before
    scoring — manual search skips both the filter and the cutoff entirely, see
    `search_media_file_subtitle.py`.

    Movies get their search anchored on `Movie.imdb_id` — the precise, single-title
    lookup OpenSubtitles' API is built around. Series get their episode's season/episode
    number instead, via `media_library.locate.resolve_media_file_episode` (a live
    Sonarr lookup, `None` when it can't be resolved) — most providers still ignore it
    and search title-only, so `pick_best_match`'s cutoff is still what keeps a wrong
    episode's subtitle from being accepted for those; TVsubtitles is the first
    provider that actually anchors its search on it.
    `SubtitleProviderConfig.use_hash` (OpenSubtitles' own `moviehash`, computed from
    `video_path` when reachable) applies to either media type. Series also carry
    `Series.tvdb_id` straight through as `tvdb_id` — every provider but Anime Tosho
    ignores it the same way most ignore season/episode.

    This never runs automatically from `translate_media_file` — that unification is
    0.11.0/0.12.0 roadmap work; this is a standalone, explicitly-triggered step (see
    `subtitle_acquisition/jobs.py`).

    When every source language comes up empty (no configured provider, or none found an
    above-cutoff match) and the profile's `speech_to_text_fallback` (ROADMAP.md 0.15.0)
    is on, a local Whisper transcription of the media file's own audio is tried once —
    see `_attempt_speech_to_text_fallback`. Unlike a provider download, this never writes
    an `AcquiredSubtitle`/`AcquisitionAttempt` row: those tables record a release's
    provenance (name, download id, match score), none of which exists for a locally
    generated transcript — same posture as the 0.14.0 OCR pipeline, which also never
    writes one.

    `on_progress`, when given, is called `(current, total, language, provider)` — 1-indexed,
    `provider=None` — once per source language attempted, and again with `provider` set to
    each provider's name as `_search_and_download` tries it for that language. ROADMAP.md
    0.20.0's "Live progress": `subtitle_acquisition.jobs.run_acquisition` is the only caller
    that passes one, wiring it into `scheduling.running_tasks.report_progress`.
    """
    profile = resolve_media_file_profile(session, media_file)
    if profile is None:
        logger.info("acquisition skipped: media file %d has no language profile", media_file.id)
        return AcquisitionResult(skipped_reason="no_language_profile")
    assert media_file.id is not None

    if _has_source_language_subtitle(session, media_file, profile.source_language_list):
        return AcquisitionResult()

    chain = resolve_subtitle_provider_chain(session)
    if not chain and not profile.speech_to_text_fallback:
        logger.info(
            "acquisition skipped: media file %d has no subtitle provider configured",
            media_file.id,
        )
        return AcquisitionResult(skipped_reason="no_provider_configured")

    try:
        context = (
            resolve_subtitle_search_context(session, media_file, video_path) if chain else None
        )
        total_languages = len(profile.source_language_list)
        for current_language, language in enumerate(profile.source_language_list, start=1):
            if context is None:
                break
            if on_progress is not None:
                on_progress(current_language, total_languages, language, None)
            result = _search_and_download(
                session,
                media_file.id,
                chain,
                context.title,
                language,
                context.imdb_id,
                context.moviehash,
                context.season_number,
                context.episode_number,
                video_path,
                context.tvdb_id,
                profile.must_contain_terms,
                profile.must_not_contain_terms,
                on_progress,
                current_language,
                total_languages,
            )
            if result is None:
                continue
            output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}.srt")
            output_path.write_text(result.content, encoding="utf-8")
            scan_subtitles_for_media_file(session, media_file, video_path)
            record_acquired_subtitle(
                session,
                media_file.id,
                language,
                provider=result.provider,
                release_name=result.release_name,
                download_id=result.download_id,
                evaluation=result.evaluation,
            )
            return AcquisitionResult(acquired_language=language)
    finally:
        # Most providers open/close a client per call; one that instead holds a
        # session for its whole lifetime (Addic7ed, logged-in cookies) exposes
        # `close()` for this — nothing else in the chain's lifecycle calls it.
        for provider in chain:
            close = getattr(provider, "close", None)
            if close is not None:
                close()

    if profile.speech_to_text_fallback:
        transcribed_language = _attempt_speech_to_text_fallback(
            media_file.id,
            video_path,
            profile.source_language_list,
            model_size=speech_to_text_model_size,
            model_dir=speech_to_text_model_dir,
            timeout_seconds=speech_to_text_timeout_seconds,
        )
        if transcribed_language is not None:
            scan_subtitles_for_media_file(session, media_file, video_path)
            return AcquisitionResult(acquired_language=transcribed_language)

    logger.info(
        "acquisition failed: media file %d found no above-cutoff match in any source language",
        media_file.id,
    )
    return AcquisitionResult(
        skipped_reason="no_provider_configured" if not chain else "no_match_found"
    )


def _has_source_language_subtitle(
    session: Session, media_file: MediaFile, source_languages: list[str]
) -> bool:
    existing_languages = set(
        session.exec(select(Subtitle.language).where(Subtitle.media_file_id == media_file.id)).all()
    )
    return any(language.lower() in existing_languages for language in source_languages)


def _attempt_speech_to_text_fallback(
    media_file_id: int,
    video_path: Path,
    source_languages: list[str],
    *,
    model_size: str,
    model_dir: Path,
    timeout_seconds: float,
) -> str | None:
    """Transcribe `video_path`'s own audio as the last-resort source subtitle, once.

    Picks the first embedded audio track whose container language tag
    (`probe_embedded_audio`, normalized via `language_codes.normalize_language_code`)
    matches one of `source_languages`, in that priority order; when nothing tags-matches
    (embedded language metadata is frequently missing or wrong), falls back to the
    container's first audio track, transcribed as the profile's first source language —
    the best guess available without a real tag to go on.

    Returns the language it wrote a subtitle for, or `None` for any of: no audio track at
    all, extraction failed (missing `ffmpeg`), or transcription produced nothing
    (missing model / timed out / no intelligible speech) — every case logged by the
    functions it calls, not re-logged here.
    """
    tracks = probe_embedded_audio_tracks(video_path, timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS)
    if not tracks:
        logger.info(
            "speech-to-text fallback skipped: media file %d has no embedded audio track",
            media_file_id,
        )
        return None

    track, language = _pick_audio_track(tracks, source_languages)
    audio_path = video_path.with_name(f"{video_path.stem}.stt.tmp.wav")
    output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}.srt")
    try:
        extract_audio_track(
            video_path, track, audio_path, timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS
        )
        if not audio_path.is_file():
            return None
        transcribe_audio_track(
            audio_path,
            language,
            output_path,
            model_size=model_size,
            model_dir=model_dir,
            timeout_seconds=timeout_seconds,
        )
    finally:
        audio_path.unlink(missing_ok=True)

    if not output_path.is_file():
        return None
    logger.info(
        "speech-to-text fallback acquired media file %d: language=%r (track language tag=%r)",
        media_file_id,
        language,
        track.language,
    )
    return language


def _pick_audio_track(
    tracks: list[EmbeddedAudioTrack], source_languages: list[str]
) -> tuple[EmbeddedAudioTrack, str]:
    for language in source_languages:
        for track in tracks:
            if normalize_language_code(track.language) == language.strip().lower():
                return track, language
    return tracks[0], source_languages[0]


def _search_and_download(
    session: Session,
    media_file_id: int,
    chain: list[SubtitleProvider],
    title: str,
    language: str,
    imdb_id: str | None,
    moviehash: str | None,
    season: int | None,
    episode: int | None,
    video_path: Path,
    tvdb_id: int | None,
    must_contain: list[str],
    must_not_contain: list[str],
    on_progress: Callable[[int, int, str, str | None], None] | None = None,
    progress_current: int = 0,
    progress_total: int = 0,
) -> _AcquiredCandidate | None:
    blacklisted = list_blacklisted_download_ids(session, media_file_id, language)
    last_error: Exception | None = None
    last_provider_name: str | None = None
    for provider in chain:
        if is_open(BreakerCategory.ACQUISITION, provider.name):
            logger.info(
                "subtitle provider %r circuit open, skipping search for %r (%s)",
                provider.name,
                title,
                language,
            )
            continue
        try:
            if on_progress is not None:
                on_progress(progress_current, progress_total, language, provider.name)
            candidates = provider.search(
                title,
                language,
                imdb_id=imdb_id,
                moviehash=moviehash,
                season=season,
                episode=episode,
                video_path=video_path,
                tvdb_id=tvdb_id,
            )
            record_success(BreakerCategory.ACQUISITION, provider.name)
            candidates = [
                candidate
                for candidate in candidates
                if passes_release_name_filters(
                    candidate.release_name, must_contain, must_not_contain
                )
                and (provider.name, candidate.download_id) not in blacklisted
            ]
            best = pick_best_match(candidates, video_path.stem)
            if best is None:
                continue
            content = provider.download(best)
            if not passes_quality_gate(content):
                logger.warning(
                    "subtitle from %r failed quality-gate checks (%r), trying next",
                    provider.name,
                    best.release_name,
                )
                continue
            return _AcquiredCandidate(
                content=content,
                provider=provider.name,
                release_name=best.release_name,
                download_id=best.download_id,
                evaluation=evaluate_candidate(best, video_path.stem),
            )
        except Exception as exc:
            record_failure(BreakerCategory.ACQUISITION, provider.name)
            last_error = exc
            last_provider_name = provider.name
            logger.warning(
                "subtitle provider %r failed searching %r (%s), trying next",
                provider.name,
                title,
                language,
            )
    if last_error is not None:
        record_acquisition_failure(
            session,
            media_file_id,
            language=language,
            error_message=f"{last_provider_name}: {last_error}",
            failed_at=datetime.now(UTC),
        )
    return None
