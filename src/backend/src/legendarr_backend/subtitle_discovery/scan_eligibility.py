from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.models import SubtitleScanState


def _utcnow() -> datetime:
    """Aware UTC `now` — `SubtitleScanState.probed_at` is read back as an aware UTC value
    (sqlmodel's `UTCDateTime`), so compare against an aware `now` (same convention as
    `authentication.manage_authentication._utcnow`)."""
    return datetime.now(UTC)


def needs_subtitle_scan(session: Session, media_file: MediaFile, recheck_after: timedelta) -> bool:
    """Whether `media_file` should be (re-)probed by the subtitle scan.

    `True` when it's never been probed, its size has changed since the last probe (the
    video was replaced — embedded tracks may have changed), or the last probe is older
    than `recheck_after` (so a manually-dropped external subtitle still gets picked up
    eventually, without re-probing embedded tracks on every fan-out tick).
    """
    state = session.exec(
        select(SubtitleScanState).where(SubtitleScanState.media_file_id == media_file.id)
    ).first()
    if state is None:
        return True
    if state.probed_size_bytes != media_file.size_bytes:
        return True
    return _utcnow() - state.probed_at >= recheck_after


def has_completed_subtitle_scan(session: Session, media_file_id: int) -> bool:
    """Whether `media_file_id` has been probed by the subtitle scan at least once.

    The readiness gate `subtitle_acquisition`/`subtitle_translation`'s periodic
    fan-outs check before considering a file — discovery must run first, so they never
    mistake "not scanned yet" for "nothing to acquire/translate".
    """
    state = session.exec(
        select(SubtitleScanState).where(SubtitleScanState.media_file_id == media_file_id)
    ).first()
    return state is not None
