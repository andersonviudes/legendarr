from datetime import UTC, datetime

from sqlmodel import Session, select

from legendarr_backend.subtitle_acquisition.models import SubtitleBlacklistEntry

# `SubtitleBlacklistEntry.origin` is a plain `str` column (see `models.py`), validated
# against these two values here rather than in the schema itself.
ACQUIRED = "acquired"
TRANSLATED = "translated"


def add_blacklist_entry(
    session: Session,
    *,
    media_file_id: int,
    language: str,
    origin: str,
    provider: str | None = None,
    release_name: str | None = None,
    download_id: str | None = None,
) -> SubtitleBlacklistEntry:
    entry = SubtitleBlacklistEntry(
        media_file_id=media_file_id,
        language=language.lower(),
        origin=origin,
        provider=provider,
        release_name=release_name,
        download_id=download_id,
        blacklisted_at=datetime.now(UTC),
    )
    session.add(entry)
    return entry


def list_blacklisted_download_ids(
    session: Session, media_file_id: int, language: str
) -> set[tuple[str, str]]:
    """`(provider, download_id)` pairs blacklisted for this media file/language — a
    search candidate matching one of these is excluded from both the automatic
    acquisition path and the manual search/upgrade ones, so it's never re-fetched.
    """
    rows = session.exec(
        select(SubtitleBlacklistEntry).where(
            SubtitleBlacklistEntry.media_file_id == media_file_id,
            SubtitleBlacklistEntry.language == language.lower(),
            SubtitleBlacklistEntry.origin == ACQUIRED,
        )
    ).all()
    return {(row.provider, row.download_id) for row in rows if row.provider and row.download_id}


def is_translation_blacklisted(session: Session, media_file_id: int, language: str) -> bool:
    """Whether a translated subtitle in `language` was blacklisted for this media file —
    blocks the periodic translation job from silently regenerating it (see
    `translate_media_file.py`); an explicit manual retranslate clears it instead via
    `clear_translation_blacklist`.
    """
    return (
        session.exec(
            select(SubtitleBlacklistEntry.id).where(
                SubtitleBlacklistEntry.media_file_id == media_file_id,
                SubtitleBlacklistEntry.language == language.lower(),
                SubtitleBlacklistEntry.origin == TRANSLATED,
            )
        ).first()
        is not None
    )


def clear_translation_blacklist(session: Session, media_file_id: int, language: str) -> None:
    rows = session.exec(
        select(SubtitleBlacklistEntry).where(
            SubtitleBlacklistEntry.media_file_id == media_file_id,
            SubtitleBlacklistEntry.language == language.lower(),
            SubtitleBlacklistEntry.origin == TRANSLATED,
        )
    ).all()
    for row in rows:
        session.delete(row)
