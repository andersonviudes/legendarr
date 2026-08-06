import logging
from collections import defaultdict

from sqlmodel import Session, select

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
from legendarr_backend.subtitle_discovery.models import Subtitle

logger = logging.getLogger(__name__)


def get_movie_detail(session: Session, movie_id: int) -> MovieDetailRead | None:
    movie = session.get(Movie, movie_id)
    if movie is None:
        return None
    files = _media_file_reads(
        session, session.exec(select(MediaFile).where(MediaFile.movie_id == movie_id)).all()
    )
    metadata = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie_id)).first()
    profile_name, target_languages = _profile_fields(session, movie)
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
    media_files = session.exec(select(MediaFile).where(MediaFile.series_id == series_id)).all()
    files = _media_file_reads(session, media_files)
    files_by_path = {
        media_file.relative_path: file_read
        for media_file, file_read in zip(media_files, files, strict=True)
    }
    metadata = session.exec(
        select(MediaMetadata).where(MediaMetadata.series_id == series_id)
    ).first()
    profile_name, target_languages = _profile_fields(session, series)
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
    try:
        episodes = client.list_episodes(series.arr_id)
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


def _media_file_reads(session: Session, media_files: list[MediaFile]) -> list[MediaFileRead]:
    media_file_ids = [media_file.id for media_file in media_files]
    subtitles_by_file_id: dict[int, list[Subtitle]] = defaultdict(list)
    for subtitle in session.exec(
        select(Subtitle).where(Subtitle.media_file_id.in_(media_file_ids))
    ).all():
        subtitles_by_file_id[subtitle.media_file_id].append(subtitle)
    return [
        MediaFileRead(
            id=media_file.id,
            relative_path=media_file.relative_path,
            size_bytes=media_file.size_bytes,
            subtitles=[
                SubtitleRead(language=subtitle.language, origin=subtitle.origin.value)
                for subtitle in subtitles_by_file_id.get(media_file.id, [])
            ],
        )
        for media_file in media_files
    ]


def _missing_subtitles_count(files: list[MediaFileRead]) -> int:
    return sum(1 for file in files if not file.subtitles)
