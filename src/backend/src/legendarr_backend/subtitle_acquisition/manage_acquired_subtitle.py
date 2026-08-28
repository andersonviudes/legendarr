from datetime import UTC, datetime

from sqlmodel import Session, select

from legendarr_backend.subtitle_acquisition.audit_trail import record_acquisition_attempt
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    CandidateEvaluation,
)
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


def record_acquired_subtitle(
    session: Session,
    media_file_id: int,
    language: str,
    *,
    provider: str,
    release_name: str,
    download_id: str,
    evaluation: CandidateEvaluation,
) -> None:
    """Record (or update in place) the provenance of the external `Subtitle` just
    written for `media_file_id`/`language` by a provider download — either
    `acquire_subtitle_for_media_file`'s automatic path or `download_subtitle_candidate`'s
    manual one.

    Looks the `Subtitle` row up rather than taking its id directly, since both callers
    only have a media file/language to hand at this point (the row itself was written,
    then possibly re-read, by `scan_subtitles_for_media_file`). A no-op if that row
    can't be found — defensive, shouldn't happen since the caller just wrote it.

    Also appends an `AcquisitionAttempt` audit-trail row via `record_acquisition_attempt`
    (ROADMAP.md 0.12.0) — unlike this function's own upsert, that one never overwrites
    a prior row, so a subtitle's acquisition history (including what an upgrade
    replaced) survives.
    """
    subtitle = session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file_id,
            Subtitle.origin == SubtitleOrigin.EXTERNAL,
            Subtitle.language == language.lower(),
        )
    ).first()
    if subtitle is None:
        return
    assert subtitle.id is not None

    existing = session.exec(
        select(AcquiredSubtitle).where(AcquiredSubtitle.subtitle_id == subtitle.id)
    ).first()
    now = datetime.now(UTC)
    if existing is None:
        session.add(
            AcquiredSubtitle(
                subtitle_id=subtitle.id,
                provider=provider,
                release_name=release_name,
                download_id=download_id,
                score=evaluation.score,
                acquired_at=now,
            )
        )
    else:
        existing.provider = provider
        existing.release_name = release_name
        existing.download_id = download_id
        existing.score = evaluation.score
        existing.acquired_at = now
        session.add(existing)

    record_acquisition_attempt(
        session,
        subtitle.id,
        provider=provider,
        release_name=release_name,
        download_id=download_id,
        evaluation=evaluation,
        attempted_at=now,
    )


def get_acquired_subtitle(session: Session, subtitle_id: int) -> AcquiredSubtitle | None:
    return session.exec(
        select(AcquiredSubtitle).where(AcquiredSubtitle.subtitle_id == subtitle_id)
    ).first()
