import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.models import EmbeddedTrack, Subtitle, SubtitleScanState
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    DEFAULT_PROBE_TIMEOUT_SECONDS,
)
from legendarr_backend.subtitle_discovery.scan_video_subtitles import (
    SubtitleOrigin,
    scan_video_subtitles,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    added: int
    removed: int
    skipped: bool = False


def scan_subtitles_for_media_file(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    *,
    probe_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    ocr_cue_timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
    force_track_index: int | None = None,
) -> ScanResult:
    """Discover external subtitles next to `video_path` and reconcile `Subtitle` rows.

    A missing video file means an unmounted drive or a stale row not yet rescanned,
    not deleted subtitles — the scan skips the file and keeps its rows, mirroring
    `scan_media_item`'s unmounted-drive guard. `relative_path` is derived from
    `media_file.relative_path`'s directory, same convention as `MediaFile` itself, so
    a subtitle row survives a path-mapping edit.

    Embedded-track probing/extraction is additionally gated by the file's effective
    `LanguageProfile`: skipped entirely when there's no effective profile, or when
    `extract_embedded_subtitles` is `False` — external scanning happens regardless, same
    as before. When it does run, a track whose language already has an external subtitle
    is skipped instead of extracted (see `scan_video_subtitles`).

    OCR of bitmap-based (PGS) tracks is gated the same way, separately, by
    `LanguageProfile.ocr_embedded_subtitles` — a profile can enable either flag
    independently of the other.

    Extraction/OCR is further restricted to the profile's `source_language_list` — a
    detected track outside it is recorded (see below) but never extracted. Every track
    `ffprobe` detects, extracted or not, is reconciled into `EmbeddedTrack` the same
    add/update/remove-stale way `Subtitle` rows are, so the UI can show what the container
    has even when most of it was skipped.

    `force_track_index`, when set, is the manual "extract this track anyway" override —
    passed straight through to `scan_video_subtitles`, which bypasses every gate above for
    that one track. See its docstring for the full behavior.
    """
    if not video_path.is_file():
        logger.warning("subtitle scan skipped: %s is not a file", video_path)
        return ScanResult(added=0, removed=0, skipped=True)
    assert media_file.id is not None

    existing_rows = list(
        session.exec(select(Subtitle).where(Subtitle.media_file_id == media_file.id))
    )
    existing = {row.relative_path: row for row in existing_rows}
    # External only — an already-extracted embedded row must not count as "already have
    # this language" for itself, or it would get skipped (and then deleted as stale) on
    # every following scan.
    known_languages = frozenset(
        row.language for row in existing_rows if row.origin == SubtitleOrigin.EXTERNAL
    )

    profile = resolve_media_file_profile(session, media_file)
    extract_embedded = profile is not None and profile.extract_embedded_subtitles
    ocr_embedded = profile is not None and profile.ocr_embedded_subtitles
    source_languages = (
        frozenset(profile.source_language_list) if profile is not None else frozenset()
    )
    scan_result = scan_video_subtitles(
        video_path,
        extract_embedded=extract_embedded,
        ocr_embedded=ocr_embedded,
        probe_timeout_seconds=probe_timeout_seconds,
        ocr_cue_timeout_seconds=ocr_cue_timeout_seconds,
        known_languages=known_languages,
        source_languages=source_languages,
        force_track_index=force_track_index,
    )
    video_dir = Path(media_file.relative_path).parent

    now = datetime.now(UTC)
    added = 0
    for item in scan_result.subtitles:
        relative_path = (video_dir / item.source_path.name).as_posix()
        content = item.source_path.read_bytes()
        content_hash = hashlib.sha256(content).hexdigest()
        row = existing.pop(relative_path, None)
        if row is None:
            session.add(
                Subtitle(
                    media_file_id=media_file.id,
                    language=item.language,
                    origin=item.origin,
                    relative_path=relative_path,
                    track_index=item.track_index,
                    forced=item.forced,
                    hearing_impaired=item.hearing_impaired,
                    size_bytes=len(content),
                    content_hash=content_hash,
                    scanned_at=now,
                )
            )
            added += 1
        else:
            row.language = item.language
            row.origin = item.origin
            row.track_index = item.track_index
            row.forced = item.forced
            row.hearing_impaired = item.hearing_impaired
            row.size_bytes = len(content)
            # A source that changed since the last translation invalidates the stamp
            # `translate_media_file` left — an unchanged rescan (the common case) keeps it.
            if row.content_hash != content_hash:
                row.translated_from_hash = None
            row.content_hash = content_hash
            row.scanned_at = now
            session.add(row)

    removed = 0
    for stale in existing.values():
        session.delete(stale)
        removed += 1

    existing_track_rows = list(
        session.exec(select(EmbeddedTrack).where(EmbeddedTrack.media_file_id == media_file.id))
    )
    existing_tracks = {row.track_index: row for row in existing_track_rows}
    for track in scan_result.detected_embedded_tracks:
        track_row = existing_tracks.pop(track.track_index, None)
        if track_row is None:
            session.add(
                EmbeddedTrack(
                    media_file_id=media_file.id,
                    track_index=track.track_index,
                    codec_name=track.codec_name,
                    language=track.language,
                    forced=track.forced,
                    hearing_impaired=track.hearing_impaired,
                    extracted=track.extracted,
                    scanned_at=now,
                )
            )
        else:
            track_row.codec_name = track.codec_name
            track_row.language = track.language
            track_row.forced = track.forced
            track_row.hearing_impaired = track.hearing_impaired
            track_row.extracted = track.extracted
            track_row.scanned_at = now
            session.add(track_row)
    for stale_track in existing_tracks.values():
        session.delete(stale_track)

    scan_state = session.exec(
        select(SubtitleScanState).where(SubtitleScanState.media_file_id == media_file.id)
    ).first()
    if scan_state is None:
        session.add(
            SubtitleScanState(
                media_file_id=media_file.id, probed_at=now, probed_size_bytes=media_file.size_bytes
            )
        )
    else:
        scan_state.probed_at = now
        scan_state.probed_size_bytes = media_file.size_bytes
        session.add(scan_state)

    return ScanResult(added=added, removed=removed)
