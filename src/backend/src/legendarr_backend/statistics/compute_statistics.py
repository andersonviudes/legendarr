from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, col, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_media_file_profile,
)
from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.statistics.schemas import (
    BreakdownEntry,
    CategoryStatistics,
    DailyCount,
    StatisticsRead,
)
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_translation.models import TranslationAttempt

# Fixed trend window (ROADMAP.md 0.20.0's Statistics view) — no date-range picker for v1.
DAILY_WINDOW_DAYS = 30

# Breakdown label for an attempt whose media file has no effective `LanguageProfile`
# (deleted since, or no default configured) — same "nothing assigned" case
# `resolve_media_file_profile` already returns `None` for elsewhere.
_NO_PROFILE_LABEL = "—"


@dataclass(frozen=True)
class _AttemptRecord:
    """`TranslationAttempt`/`AcquisitionAttempt` normalized to the three fields
    `_category_statistics` actually needs — lets it treat both data sources identically
    without caring that the two models spell their timestamp column differently
    (`translated_at` vs `attempted_at`)."""

    subtitle_id: int
    provider: str
    occurred_at: datetime


def compute_statistics(session: Session) -> StatisticsRead:
    """Aggregate the Statistics view's two data sources — `TranslationAttempt`
    (translated) and `AcquisitionAttempt` (acquired) — into one response. Both are
    append-only audit trails of successful outcomes only (ROADMAP.md 0.12.0/0.20.0),
    so every row here already represents a "win", not a failed candidate.
    """
    translated_records = [
        _AttemptRecord(attempt.subtitle_id, attempt.provider, attempt.translated_at)
        for attempt in session.exec(select(TranslationAttempt))
    ]
    acquired_records = [
        _AttemptRecord(attempt.subtitle_id, attempt.provider, attempt.attempted_at)
        for attempt in session.exec(select(AcquisitionAttempt))
    ]
    return StatisticsRead(
        translated=_category_statistics(session, translated_records),
        acquired=_category_statistics(session, acquired_records),
    )


def _category_statistics(session: Session, records: Sequence[_AttemptRecord]) -> CategoryStatistics:
    daily_counts = _zero_filled_daily_counts()
    provider_counts: Counter[str] = Counter()
    profile_counts: Counter[str] = Counter()
    profile_label_by_subtitle_id = _profile_labels_by_subtitle_id(
        session, {record.subtitle_id for record in records}
    )

    for record in records:
        provider_counts[record.provider] += 1
        profile_counts[profile_label_by_subtitle_id.get(record.subtitle_id, _NO_PROFILE_LABEL)] += 1
        occurred_on = record.occurred_at.date()
        if occurred_on in daily_counts:
            daily_counts[occurred_on] += 1

    return CategoryStatistics(
        total=len(records),
        daily=[DailyCount(date=day, count=count) for day, count in daily_counts.items()],
        by_profile=_sorted_breakdown(profile_counts),
        by_provider=_sorted_breakdown(provider_counts),
    )


def _zero_filled_daily_counts() -> dict[date, int]:
    """One entry per day in the trend window, oldest first, all starting at zero —
    so a quiet day still shows up as a zero-height bar instead of a gap."""
    today = datetime.now(UTC).date()
    return {today - timedelta(days=offset): 0 for offset in range(DAILY_WINDOW_DAYS - 1, -1, -1)}


def _profile_labels_by_subtitle_id(session: Session, subtitle_ids: set[int]) -> dict[int, str]:
    """Every attempt's `subtitle_id` resolved to its media file's *current* effective
    `LanguageProfile` name — same live-resolution approximation
    `media_library.list_wanted_media` already uses, not a historical snapshot (neither
    attempt table stores a profile_id). Resolved once per distinct media file, not once
    per attempt, since several attempts commonly share one.
    """
    if not subtitle_ids:
        return {}
    subtitles = session.exec(select(Subtitle).where(col(Subtitle.id).in_(subtitle_ids))).all()
    media_files = session.exec(
        select(MediaFile).where(col(MediaFile.id).in_({s.media_file_id for s in subtitles}))
    ).all()

    label_by_media_file_id: dict[int, str] = {}
    for media_file in media_files:
        assert media_file.id is not None
        profile = resolve_media_file_profile(session, media_file)
        label_by_media_file_id[media_file.id] = (
            profile.name if profile is not None else _NO_PROFILE_LABEL
        )

    return {
        subtitle.id: label_by_media_file_id.get(subtitle.media_file_id, _NO_PROFILE_LABEL)
        for subtitle in subtitles
        if subtitle.id is not None
    }


def _sorted_breakdown(counts: Counter[str]) -> list[BreakdownEntry]:
    """Highest count first, label alphabetical as the tiebreaker — stable ordering run
    to run instead of `Counter`'s insertion-order-ish iteration."""
    return [
        BreakdownEntry(label=label, count=count)
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
