from collections.abc import Iterable

from sqlmodel import Session, col, select

from legendarr_backend.media_library.locate import resolve_media_file_display_name
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_discovery.models import Subtitle

# `job_id` prefix -> what its remainder identifies, mirroring each slice's own
# `jobs.py` convention (`subtitle_scan:<media_file_id>`, `media_scan:<kind>:<id>`, ...).
# A prefix not listed here — a periodic fan-out's own job id, e.g.
# `subtitle_discovery_scan_fanout` — is already a readable name on its own, left alone.
_MEDIA_FILE_JOB_PREFIXES = {
    "subtitle_scan",
    "subtitle_acquisition",
    "subtitle_translation",
    "subtitle_upgrade",
}
_SUBTITLE_JOB_PREFIX = "subtitle_timing_sync"
_SERIES_JOB_PREFIX = "pending_subtitle_reconcile"
_MEDIA_ITEM_JOB_PREFIXES = {"media_scan", "media_metadata_fetch"}


def resolve_job_media_titles(session: Session, job_ids: Iterable[str]) -> dict[str, str]:
    """Every `job_id` in `job_ids` that names a specific media item, mapped to its
    display title — for the System > Tasks page (both the live queue and job history),
    so a job reads as "The Rings of Power — S01E03.mkv" instead of `subtitle_scan:63`.

    A `job_id` with an unrecognized prefix, or naming media deleted since the job was
    enqueued, is simply absent from the result — same skip-don't-fail posture as
    `media_library.locate`'s resolvers; the caller falls back to the raw `job_id`/the
    job's own `name`.
    """
    media_file_ids: dict[str, int] = {}
    subtitle_ids: dict[str, int] = {}
    series_ids: dict[str, int] = {}
    media_items: dict[str, tuple[str, int]] = {}

    for job_id in job_ids:
        parts = job_id.split(":")
        prefix = parts[0]
        if prefix in _MEDIA_FILE_JOB_PREFIXES and len(parts) == 2:
            media_file_ids[job_id] = int(parts[1])
        elif prefix == _SUBTITLE_JOB_PREFIX and len(parts) == 2:
            subtitle_ids[job_id] = int(parts[1])
        elif prefix == _SERIES_JOB_PREFIX and len(parts) == 2:
            series_ids[job_id] = int(parts[1])
        elif prefix in _MEDIA_ITEM_JOB_PREFIXES and len(parts) == 3:
            media_items[job_id] = (parts[1], int(parts[2]))

    titles: dict[str, str] = {}
    titles.update(_media_file_titles(session, media_file_ids, subtitle_ids))
    titles.update(_series_titles(session, series_ids))
    titles.update(_media_item_titles(session, media_items))
    return titles


def _media_file_titles(
    session: Session, media_file_ids: dict[str, int], subtitle_ids: dict[str, int]
) -> dict[str, str]:
    """Titles for `subtitle_scan`/`subtitle_acquisition`/`subtitle_translation`/
    `subtitle_upgrade` job ids (keyed by `MediaFile.id` directly) and `subtitle_timing_sync`
    job ids (keyed by `Subtitle.id`, one hop away from its `MediaFile`) — batched into the
    same two queries regardless of which job types are actually present.
    """
    if not media_file_ids and not subtitle_ids:
        return {}
    wanted_media_file_ids = set(media_file_ids.values())
    media_file_id_by_subtitle_id: dict[int, int] = {}
    if subtitle_ids:
        subtitles = session.exec(
            select(Subtitle).where(col(Subtitle.id).in_(subtitle_ids.values()))
        ).all()
        media_file_id_by_subtitle_id = {
            subtitle.id: subtitle.media_file_id for subtitle in subtitles if subtitle.id is not None
        }
        wanted_media_file_ids |= set(media_file_id_by_subtitle_id.values())
    media_files_by_id = {
        media_file.id: media_file
        for media_file in session.exec(
            select(MediaFile).where(col(MediaFile.id).in_(wanted_media_file_ids))
        )
        if media_file.id is not None
    }

    titles: dict[str, str] = {}
    for job_id, media_file_id in media_file_ids.items():
        media_file = media_files_by_id.get(media_file_id)
        if media_file is None:
            continue
        title = resolve_media_file_display_name(session, media_file)
        if title is not None:
            titles[job_id] = title
    for job_id, subtitle_id in subtitle_ids.items():
        media_file_id = media_file_id_by_subtitle_id.get(subtitle_id)
        media_file = media_files_by_id.get(media_file_id) if media_file_id is not None else None
        if media_file is None:
            continue
        title = resolve_media_file_display_name(session, media_file)
        if title is not None:
            titles[job_id] = title
    return titles


def _series_titles(session: Session, series_ids: dict[str, int]) -> dict[str, str]:
    """Titles for `pending_subtitle_reconcile` job ids, keyed by `Series.id` directly."""
    if not series_ids:
        return {}
    series_titles_by_id = {
        series.id: series.title
        for series in session.exec(select(Series).where(col(Series.id).in_(series_ids.values())))
    }
    return {
        job_id: series_titles_by_id[series_id]
        for job_id, series_id in series_ids.items()
        if series_id in series_titles_by_id
    }


def _media_item_titles(session: Session, media_items: dict[str, tuple[str, int]]) -> dict[str, str]:
    """Titles for `media_scan`/`media_metadata_fetch` job ids, keyed by a
    `(media_kind, media_id)` pair pointing straight at a `Movie` or `Series` row."""
    if not media_items:
        return {}
    movie_ids = {media_id for kind, media_id in media_items.values() if kind == "movie"}
    series_ids = {media_id for kind, media_id in media_items.values() if kind == "series"}
    movie_titles_by_id = {
        movie.id: movie.title
        for movie in session.exec(select(Movie).where(col(Movie.id).in_(movie_ids)))
    }
    series_titles_by_id = {
        series.id: series.title
        for series in session.exec(select(Series).where(col(Series.id).in_(series_ids)))
    }
    titles: dict[str, str] = {}
    for job_id, (kind, media_id) in media_items.items():
        title = (
            movie_titles_by_id.get(media_id)
            if kind == "movie"
            else series_titles_by_id.get(media_id)
        )
        if title is not None:
            titles[job_id] = title
    return titles
