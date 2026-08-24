from datetime import datetime

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_acquisition.match_score import CandidateEvaluation
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt


def record_acquisition_attempt(
    session: Session,
    subtitle_id: int,
    *,
    provider: str,
    release_name: str,
    download_id: str,
    evaluation: CandidateEvaluation,
    attempted_at: datetime,
) -> None:
    """Append one `AcquisitionAttempt` row for the winning candidate
    `manage_acquired_subtitle.record_acquired_subtitle` just upserted into
    `AcquiredSubtitle` — never updates an existing row, unlike that function, so a
    subtitle's acquisition history survives every later upgrade.

    `replaced_attempt_id` is set to the subtitle's most recent prior attempt (if any),
    linking an upgraded subtitle back to the one it replaced.
    """
    previous = _latest_attempt(session, subtitle_id)
    session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle_id,
            provider=provider,
            release_name=release_name,
            download_id=download_id,
            score=evaluation.score,
            title_similarity=evaluation.title_similarity,
            resolution_matched=evaluation.attribute_matches.get("resolution"),
            source_matched=evaluation.attribute_matches.get("source"),
            codec_matched=evaluation.attribute_matches.get("codec"),
            release_group_matched=evaluation.attribute_matches.get("release_group"),
            edition_matched=evaluation.attribute_matches.get("edition"),
            replaced_attempt_id=previous.id if previous is not None else None,
            attempted_at=attempted_at,
        )
    )


def list_acquisition_attempts(session: Session, subtitle_id: int) -> list[AcquisitionAttempt]:
    """Every `AcquisitionAttempt` recorded for `subtitle_id`, oldest first — the full
    audit trail a later upgrade's `replaced_attempt_id` chain can be walked from.
    """
    return list(
        session.exec(
            select(AcquisitionAttempt)
            .where(AcquisitionAttempt.subtitle_id == subtitle_id)
            .order_by(col(AcquisitionAttempt.id))
        ).all()
    )


def _latest_attempt(session: Session, subtitle_id: int) -> AcquisitionAttempt | None:
    return session.exec(
        select(AcquisitionAttempt)
        .where(AcquisitionAttempt.subtitle_id == subtitle_id)
        .order_by(col(AcquisitionAttempt.id).desc())
    ).first()
