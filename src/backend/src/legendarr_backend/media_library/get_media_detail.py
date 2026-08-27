import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

from sqlmodel import Session, col, select

from legendarr_backend.arr_clients.base import SeriesLibraryClient
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_effective_profile,
)
from legendarr_backend.media_library.list_media_library import metadata_fields
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.media_library.schemas import (
    EpisodeRead,
    MediaFileRead,
    MovieDetailRead,
    SeriesDetailRead,
    SubtitleRead,
)
from legendarr_backend.media_metadata.models import MediaMetadata
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle, AcquisitionAttempt
from legendarr_backend.subtitle_discovery.models import Subtitle

logger = logging.getLogger(__name__)


def get_movie_detail(session: Session, movie_id: int) -> MovieDetailRead | None:
    movie = session.get(Movie, movie_id)
    if movie is None:
        return None
    assert movie.id is not None
    profile_name, target_languages = _profile_fields(session, movie)
    files = _media_file_reads(
        session,
        session.exec(select(MediaFile).where(MediaFile.movie_id == movie_id)).all(),
        target_languages,
    )
    metadata = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie_id)).first()
    return MovieDetailRead(
        id=movie.id,
        title=movie.title,
        monitored=movie.monitored,
        status=movie.status,
        quality_profile_name=movie.quality_profile_name,
        **metadata_fields(metadata),
        remote_path=movie.remote_path,
        language_profile_name=profile_name,
        target_languages=target_languages,
        missing_subtitles_count=_missing_subtitles_count(files),
        files=files,
    )


def get_series_detail(session: Session, series_id: int) -> SeriesDetailRead | None:
    series = session.get(Series, series_id)
    if series is None:
        return None
    assert series.id is not None
    profile_name, target_languages = _profile_fields(session, series)
    media_files = session.exec(select(MediaFile).where(MediaFile.series_id == series_id)).all()
    files = _media_file_reads(session, media_files, target_languages)
    files_by_path = {
        media_file.relative_path: file_read
        for media_file, file_read in zip(media_files, files, strict=True)
    }
    metadata = session.exec(
        select(MediaMetadata).where(MediaMetadata.series_id == series_id)
    ).first()
    episodes, episodes_unavailable = _episode_reads(session, series, files_by_path)
    return SeriesDetailRead(
        id=series.id,
        title=series.title,
        monitored=series.monitored,
        status=series.status,
        quality_profile_name=series.quality_profile_name,
        episode_count=series.episode_count,
        episode_file_count=series.episode_file_count,
        **metadata_fields(metadata),
        remote_path=series.remote_path,
        language_profile_name=profile_name,
        target_languages=target_languages,
        missing_subtitles_count=_missing_subtitles_count(files),
        episodes=episodes,
        episodes_unavailable=episodes_unavailable,
    )


def _episode_reads(
    session: Session, series: Series, files_by_path: dict[str, MediaFileRead]
) -> tuple[list[EpisodeRead], bool]:
    """Live-fetched from Sonarr — no `Episode` entity is persisted (see `ROADMAP.md`).

    Returns `([], False)` when the series' connection no longer exists, the same
    skip-don't-fail treatment `resolve_media_file_path` gives a deleted connection, and
    `([], True)` when the connection exists but Sonarr couldn't be reached — the caller
    surfaces that as "episodes unavailable" instead of "no episodes yet".
    """
    arr_service = session.get(ArrService, series.arr_service_id)
    if arr_service is None:
        return [], False
    client = build_client(arr_service)
    # `series` is only ever synced from a Sonarr connection (see
    # `sync_media_library.MEDIA_MODEL_BY_TYPE`), so `client` is always a
    # `SeriesLibraryClient` here even though `build_client`'s declared return type is
    # the broader `RadarrClient | SonarrClient` union.
    sonarr_client = cast(SeriesLibraryClient, client)
    try:
        episodes = sonarr_client.list_episodes(series.arr_id)
    except ProviderClientError:
        logger.warning(
            "couldn't fetch episodes for series %r (%s) from Sonarr", series.title, series.arr_id
        )
        return [], True
    finally:
        client.close()
    return [
        EpisodeRead(
            season_number=episode.season_number,
            episode_number=episode.episode_number,
            title=episode.title,
            media_file=files_by_path.get(episode.relative_path) if episode.relative_path else None,
        )
        for episode in episodes
    ], False


def _profile_fields(session: Session, item: Movie | Series) -> tuple[str | None, list[str]]:
    profile = resolve_effective_profile(session, item)
    if profile is None:
        return None, []
    return profile.name, profile.target_language_list


def _media_file_reads(
    session: Session, media_files: Sequence[MediaFile], target_languages: list[str]
) -> list[MediaFileRead]:
    media_file_ids: list[int] = []
    for media_file in media_files:
        assert media_file.id is not None
        media_file_ids.append(media_file.id)
    subtitles_by_file_id: dict[int, list[Subtitle]] = defaultdict(list)
    for subtitle in session.exec(
        select(Subtitle).where(col(Subtitle.media_file_id).in_(media_file_ids))
    ).all():
        subtitles_by_file_id[subtitle.media_file_id].append(subtitle)
    subtitle_ids = [
        subtitle.id for subtitles in subtitles_by_file_id.values() for subtitle in subtitles
    ]
    acquired_by_subtitle_id: dict[int, AcquiredSubtitle] = {
        acquired.subtitle_id: acquired
        for acquired in session.exec(
            select(AcquiredSubtitle).where(col(AcquiredSubtitle.subtitle_id).in_(subtitle_ids))
        ).all()
    }
    # `AcquisitionAttempt` is append-only and always written in lockstep with
    # `AcquiredSubtitle` (see `manage_acquired_subtitle.record_acquired_subtitle`), so the
    # highest-id attempt for a subtitle is always the one behind its current
    # `AcquiredSubtitle` row — iterating oldest-first and overwriting the dict lands on
    # that one without a second query per subtitle.
    attempts_by_subtitle_id: dict[int, AcquisitionAttempt] = {}
    for attempt in session.exec(
        select(AcquisitionAttempt)
        .where(col(AcquisitionAttempt.subtitle_id).in_(subtitle_ids))
        .order_by(col(AcquisitionAttempt.id))
    ).all():
        attempts_by_subtitle_id[attempt.subtitle_id] = attempt
    reads = []
    for media_file in media_files:
        assert media_file.id is not None
        subtitle_reads = []
        for subtitle in subtitles_by_file_id.get(media_file.id, []):
            assert subtitle.id is not None
            acquired = acquired_by_subtitle_id.get(subtitle.id)
            attempt = attempts_by_subtitle_id.get(subtitle.id)
            subtitle_reads.append(
                SubtitleRead(
                    id=subtitle.id,
                    language=subtitle.language,
                    origin=subtitle.origin.value,
                    size_bytes=subtitle.size_bytes,
                    provider=acquired.provider if acquired else None,
                    release_name=acquired.release_name if acquired else None,
                    score=acquired.score if acquired else None,
                    resolution_matched=attempt.resolution_matched if attempt else None,
                    source_matched=attempt.source_matched if attempt else None,
                    codec_matched=attempt.codec_matched if attempt else None,
                    release_group_matched=attempt.release_group_matched if attempt else None,
                    edition_matched=attempt.edition_matched if attempt else None,
                )
            )
        present = {subtitle.language for subtitle in subtitle_reads}
        reads.append(
            MediaFileRead(
                id=media_file.id,
                relative_path=media_file.relative_path,
                size_bytes=media_file.size_bytes,
                subtitles=subtitle_reads,
                missing_languages=[
                    language for language in target_languages if language.lower() not in present
                ],
            )
        )
    return reads


def _missing_subtitles_count(files: list[MediaFileRead]) -> int:
    """Files still missing at least one of the profile's target languages — each
    file's own `missing_languages` (computed in `_media_file_reads`) already answers
    that per file."""
    return sum(1 for file in files if file.missing_languages)
