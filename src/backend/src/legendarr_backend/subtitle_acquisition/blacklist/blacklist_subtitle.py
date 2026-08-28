from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.blacklist.manage_subtitle_blacklist import (
    ACQUIRED,
    TRANSLATED,
    add_blacklist_entry,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import get_acquired_subtitle
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


def blacklist_subtitle(
    session: Session, media_file: MediaFile, video_path: Path, subtitle: Subtitle
) -> tuple[bool, str]:
    """Mark `subtitle` as bad so it's never reused or re-fetched for `media_file`
    again — ROADMAP.md 0.12.0's blacklist action.

    Only an external subtitle the system itself acquired (has an `AcquiredSubtitle`
    metadata row, see `manage_acquired_subtitle.py`) or produced by translation
    (`translated_from_hash` set) can be blacklisted; a manually uploaded or embedded
    one is rejected with `(False, message)` — same tolerant shape
    `download_subtitle_candidate`/`upload_subtitle_for_media_file` use — since there's
    no provider release to exclude and no periodic regeneration to block for those.

    Deletes the sidecar file on disk (if still there) and rescans rather than deleting
    the `Subtitle`/`AcquiredSubtitle` rows directly — the scan's own stale-row cleanup
    (`scan_subtitles_for_media_file`) reconciles them away, same as every other
    acquisition action here.
    """
    assert subtitle.id is not None
    if subtitle.origin != SubtitleOrigin.EXTERNAL:
        return False, "Only an external subtitle can be blacklisted"

    metadata = get_acquired_subtitle(session, subtitle.id)
    if metadata is not None:
        add_blacklist_entry(
            session,
            media_file_id=subtitle.media_file_id,
            language=subtitle.language,
            origin=ACQUIRED,
            provider=metadata.provider,
            release_name=metadata.release_name,
            download_id=metadata.download_id,
        )
    elif subtitle.translated_from_hash is not None:
        add_blacklist_entry(
            session,
            media_file_id=subtitle.media_file_id,
            language=subtitle.language,
            origin=TRANSLATED,
        )
    else:
        return False, "This subtitle wasn't acquired or translated, so it can't be blacklisted"

    subtitle_path = video_path.parent / Path(subtitle.relative_path).name
    subtitle_path.unlink(missing_ok=True)
    scan_subtitles_for_media_file(session, media_file, video_path)
    return True, f"Blacklisted {subtitle.language} subtitle"
