"""Assemble the `SubtitleAcquisitionResult` DTO the media library's synchronous
acquisition routes return — extracted from `router.py` so route handlers stay thin
and this provenance assembly is testable on its own.

Batches the per-subtitle provenance lookups (`AcquiredSubtitle` + latest
`AcquisitionAttempt`) into one query per table instead of two per subtitle row — the
same oldest-first-overwrite pattern `get_media_detail._media_file_reads` already uses,
so query count stays constant no matter how many subtitles the file has.
"""

from sqlmodel import Session, col, select

from legendarr_backend.media_library.schemas import (
    EmbeddedTrackRead,
    SubtitleAcquisitionResult,
    SubtitleRead,
)
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle, AcquisitionAttempt
from legendarr_backend.subtitle_discovery.list_missing_subtitles import (
    has_source_subtitle_for_media_file,
    missing_target_languages_for_media_file,
)
from legendarr_backend.subtitle_discovery.models import EmbeddedTrack, Subtitle


def build_acquisition_result(
    session: Session, media_file_id: int, success: bool, message: str
) -> SubtitleAcquisitionResult:
    """Build the full post-acquisition state of one media file: every `Subtitle` row
    with its provenance, the file's embedded tracks joined to their extracted
    subtitles by track index, and the effective profile's missing target languages /
    source-subtitle answer.

    `missing_languages`/`has_source_subtitle` are delegated to
    `subtitle_discovery.list_missing_subtitles` rather than recomputed from the loaded
    rows — those functions own the profile resolution and language-normalization
    rules, and keeping them as the single source of truth keeps this result consistent
    with everywhere else they're asked.
    """
    subtitles = session.exec(select(Subtitle).where(Subtitle.media_file_id == media_file_id)).all()
    subtitle_ids = [subtitle.id for subtitle in subtitles if subtitle.id is not None]
    acquired_by_subtitle_id: dict[int, AcquiredSubtitle] = {
        acquired.subtitle_id: acquired
        for acquired in session.exec(
            select(AcquiredSubtitle).where(col(AcquiredSubtitle.subtitle_id).in_(subtitle_ids))
        ).all()
    }
    # `AcquisitionAttempt` is append-only, so the highest-id attempt for a subtitle is
    # its latest — iterating oldest-first and overwriting the dict lands on that one
    # without a per-subtitle `ORDER BY ... DESC` query (same trick as
    # `get_media_detail._media_file_reads`).
    attempts_by_subtitle_id: dict[int, AcquisitionAttempt] = {}
    for attempt in session.exec(
        select(AcquisitionAttempt)
        .where(col(AcquisitionAttempt.subtitle_id).in_(subtitle_ids))
        .order_by(col(AcquisitionAttempt.id))
    ).all():
        attempts_by_subtitle_id[attempt.subtitle_id] = attempt
    subtitle_reads = []
    for subtitle in subtitles:
        assert subtitle.id is not None
        acquired = acquired_by_subtitle_id.get(subtitle.id)
        attempt = attempts_by_subtitle_id.get(subtitle.id)
        subtitle_reads.append(
            SubtitleRead(
                id=subtitle.id,
                language=subtitle.language,
                origin=subtitle.origin.value,
                size_bytes=subtitle.size_bytes,
                track_index=subtitle.track_index,
                provider=acquired.provider if acquired else None,
                release_name=acquired.release_name if acquired else None,
                score=acquired.score if acquired else None,
                resolution_matched=attempt.resolution_matched if attempt else None,
                source_matched=attempt.source_matched if attempt else None,
                codec_matched=attempt.codec_matched if attempt else None,
                release_group_matched=attempt.release_group_matched if attempt else None,
                edition_matched=attempt.edition_matched if attempt else None,
            )
        )
    subtitle_read_by_track_index = {
        subtitle_read.track_index: subtitle_read
        for subtitle_read in subtitle_reads
        if subtitle_read.origin == "embedded"
    }
    embedded_track_reads = [
        EmbeddedTrackRead(
            track_index=track.track_index,
            language=track.language,
            display_language=track.display_language,
            extracted=track.extracted,
            subtitle=subtitle_read_by_track_index.get(track.track_index),
        )
        for track in session.exec(
            select(EmbeddedTrack).where(EmbeddedTrack.media_file_id == media_file_id)
        ).all()
    ]
    return SubtitleAcquisitionResult(
        success=success,
        message=message,
        subtitles=subtitle_reads,
        embedded_tracks=embedded_track_reads,
        missing_languages=missing_target_languages_for_media_file(session, media_file_id),
        has_source_subtitle=has_source_subtitle_for_media_file(session, media_file_id),
    )
