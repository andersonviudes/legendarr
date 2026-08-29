from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.upload_media_file_subtitle import (
    ALLOWED_UPLOAD_SUFFIXES,
)


def upload_pending_subtitle(
    session: Session,
    series: Series,
    season_number: int,
    episode_number: int,
    language: str,
    filename: str,
    content: bytes,
) -> tuple[bool, str]:
    """Hold a user-uploaded subtitle for a series episode Sonarr hasn't downloaded yet
    as a `PendingSubtitle` — same extension allowlist and tolerant `(False, message)`
    shape as `upload_subtitle_for_media_file`, but there's no `video_path` to write
    next to yet, so the content is staged instead of written to disk.

    Replaces any `PendingSubtitle` already held for this episode/language.
    """
    assert series.id is not None
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return False, f"Unsupported file type '{suffix or filename}'"

    existing = session.exec(
        select(PendingSubtitle).where(
            PendingSubtitle.series_id == series.id,
            PendingSubtitle.season_number == season_number,
            PendingSubtitle.episode_number == episode_number,
            PendingSubtitle.language == language.lower(),
        )
    ).first()
    now = datetime.now(UTC)
    if existing is None:
        session.add(
            PendingSubtitle(
                series_id=series.id,
                season_number=season_number,
                episode_number=episode_number,
                language=language.lower(),
                filename=f"{language.lower()}{suffix}",
                content=content,
                created_at=now,
            )
        )
    else:
        existing.filename = f"{language.lower()}{suffix}"
        existing.content = content
        existing.provider = None
        existing.release_name = None
        existing.created_at = now
        session.add(existing)

    return True, f"Uploaded {language} subtitle (pending {series.title})"
