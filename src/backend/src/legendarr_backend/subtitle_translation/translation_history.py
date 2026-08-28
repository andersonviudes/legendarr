from datetime import datetime

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_translation.models import TranslationAttempt


def record_translation_attempt(
    session: Session,
    subtitle_id: int,
    *,
    provider: str,
    source_language: str,
    target_language: str,
    translated_at: datetime,
) -> None:
    """Append one `TranslationAttempt` row for a target language `translate_media_file`
    just translated — mirrors `subtitle_acquisition.audit_trail.record_acquisition_attempt`
    for the translation side of ROADMAP.md 0.20.0's Statistics view. Unlike that function,
    there's no upgrade chain to link back to: a retranslation is just another row here,
    same subtitle_id, nothing to point at.
    """
    session.add(
        TranslationAttempt(
            subtitle_id=subtitle_id,
            provider=provider,
            source_language=source_language,
            target_language=target_language,
            translated_at=translated_at,
        )
    )


def list_translation_attempts(session: Session, subtitle_id: int) -> list[TranslationAttempt]:
    """Every `TranslationAttempt` recorded for `subtitle_id`, oldest first."""
    return list(
        session.exec(
            select(TranslationAttempt)
            .where(TranslationAttempt.subtitle_id == subtitle_id)
            .order_by(col(TranslationAttempt.id))
        ).all()
    )
