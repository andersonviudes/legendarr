from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlmodel import Session, col, select

from legendarr_backend.history.schemas import HistoryEntryRead
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt, AcquisitionFailure
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_translation.models import TranslationAttempt, TranslationFailure

# Flat, capped, most-recent-first feed — no date-range/filter UI for v1, same
# "no date-range picker for v1" precedent as `statistics.compute_statistics`.
DEFAULT_LIMIT = 50

# Media title for an entry whose `MediaFile`/`Movie`/`Series` row is gone by the time
# this runs (deleted since) — same "nothing to show" fallback as
# `statistics.compute_statistics._NO_PROFILE_LABEL`.
_UNKNOWN_TITLE = "—"


@dataclass(frozen=True)
class _RawEntry:
    """One row from any of the four source tables, normalized to what `list_history`
    needs before its `media_file_id` is resolved to a title — mirrors
    `statistics.compute_statistics._AttemptRecord`.
    """

    category: Literal["translation", "acquisition"]
    status: Literal["success", "failure"]
    media_file_id: int
    language: str
    provider: str | None
    error_message: str | None
    occurred_at: datetime
    score: float | None


def list_history(session: Session, limit: int = DEFAULT_LIMIT) -> list[HistoryEntryRead]:
    """Most recent translation/acquisition attempts, successes and failures merged into
    one reverse-chronological feed — ROADMAP.md 0.20.0's History view. Each of the four
    source tables is fetched newest-first and capped at `limit` before merging, so this
    stays bounded regardless of how large any one of them has grown.
    """
    translation_wins = list(
        session.exec(
            select(TranslationAttempt)
            .order_by(col(TranslationAttempt.translated_at).desc())
            .limit(limit)
        )
    )
    translation_failures = list(
        session.exec(
            select(TranslationFailure)
            .order_by(col(TranslationFailure.failed_at).desc())
            .limit(limit)
        )
    )
    acquisition_wins = list(
        session.exec(
            select(AcquisitionAttempt)
            .order_by(col(AcquisitionAttempt.attempted_at).desc())
            .limit(limit)
        )
    )
    acquisition_failures = list(
        session.exec(
            select(AcquisitionFailure)
            .order_by(col(AcquisitionFailure.failed_at).desc())
            .limit(limit)
        )
    )

    subtitle_ids = {win.subtitle_id for win in translation_wins} | {
        win.subtitle_id for win in acquisition_wins
    }
    subtitles_by_id = _subtitles_by_id(session, subtitle_ids)

    raw_entries: list[_RawEntry] = []
    for win in translation_wins:
        subtitle = subtitles_by_id.get(win.subtitle_id)
        if subtitle is None:
            continue
        raw_entries.append(
            _RawEntry(
                category="translation",
                status="success",
                media_file_id=subtitle.media_file_id,
                language=win.target_language,
                provider=win.provider,
                error_message=None,
                occurred_at=win.translated_at,
                score=None,
            )
        )
    for failure in translation_failures:
        raw_entries.append(
            _RawEntry(
                category="translation",
                status="failure",
                media_file_id=failure.media_file_id,
                language=failure.target_language,
                provider=None,
                error_message=failure.error_message,
                occurred_at=failure.failed_at,
                score=None,
            )
        )
    for win in acquisition_wins:
        subtitle = subtitles_by_id.get(win.subtitle_id)
        if subtitle is None:
            continue
        raw_entries.append(
            _RawEntry(
                category="acquisition",
                status="success",
                media_file_id=subtitle.media_file_id,
                language=subtitle.language,
                provider=win.provider,
                error_message=None,
                occurred_at=win.attempted_at,
                score=win.score,
            )
        )
    for failure in acquisition_failures:
        raw_entries.append(
            _RawEntry(
                category="acquisition",
                status="failure",
                media_file_id=failure.media_file_id,
                language=failure.language,
                provider=None,
                error_message=failure.error_message,
                occurred_at=failure.failed_at,
                score=None,
            )
        )

    raw_entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    raw_entries = raw_entries[:limit]

    titles_by_media_file_id = _media_titles_by_file_id(
        session, {entry.media_file_id for entry in raw_entries}
    )
    return [
        HistoryEntryRead(
            category=entry.category,
            status=entry.status,
            media_title=titles_by_media_file_id.get(entry.media_file_id, _UNKNOWN_TITLE),
            language=entry.language,
            provider=entry.provider,
            error_message=entry.error_message,
            occurred_at=entry.occurred_at,
            score=entry.score,
        )
        for entry in raw_entries
    ]


def _subtitles_by_id(session: Session, subtitle_ids: set[int]) -> dict[int, Subtitle]:
    if not subtitle_ids:
        return {}
    subtitles = session.exec(select(Subtitle).where(col(Subtitle.id).in_(subtitle_ids))).all()
    return {subtitle.id: subtitle for subtitle in subtitles if subtitle.id is not None}


def _media_titles_by_file_id(session: Session, media_file_ids: set[int]) -> dict[int, str]:
    """Every `media_file_id`'s display title: the owning `Movie`/`Series`' title, plus
    the file's own filename for a series entry (an episode's title is a live Sonarr
    fetch — too expensive to make per history row, see `get_media_detail._episode_reads`).
    """
    if not media_file_ids:
        return {}
    media_files = session.exec(select(MediaFile).where(col(MediaFile.id).in_(media_file_ids))).all()
    movie_ids = {file.movie_id for file in media_files if file.movie_id is not None}
    series_ids = {file.series_id for file in media_files if file.series_id is not None}
    movie_titles = {
        movie.id: movie.title
        for movie in session.exec(select(Movie).where(col(Movie.id).in_(movie_ids)))
    }
    series_titles = {
        series.id: series.title
        for series in session.exec(select(Series).where(col(Series.id).in_(series_ids)))
    }

    titles: dict[int, str] = {}
    for file in media_files:
        assert file.id is not None
        if file.movie_id is not None:
            titles[file.id] = movie_titles.get(file.movie_id, _UNKNOWN_TITLE)
        else:
            assert file.series_id is not None
            series_title = series_titles.get(file.series_id, _UNKNOWN_TITLE)
            titles[file.id] = f"{series_title} — {Path(file.relative_path).name}"
    return titles
