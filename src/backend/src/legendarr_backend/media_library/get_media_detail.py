import logging
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

from sqlmodel import Session, col, select

from legendarr_backend.arr_clients.base import SeriesLibraryClient
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_effective_profile,
)
from legendarr_backend.media_library.list_media_library import metadata_fields
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.media_library.schemas import (
    EmbeddedTrackRead,
    EpisodeRead,
    MediaFileRead,
    MovieDetailRead,
    SeriesDetailRead,
    SubtitleRead,
)
from legendarr_backend.media_metadata.models import MediaMetadata
from legendarr_backend.subtitle_acquisition.models import (
    AcquiredSubtitle,
    AcquisitionAttempt,
    PendingSubtitle,
)
from legendarr_backend.subtitle_discovery.embedded_track_score import score_embedded_subtitle
from legendarr_backend.subtitle_discovery.models import EmbeddedTrack, Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin

logger = logging.getLogger(__name__)


def get_movie_detail(session: Session, movie_id: int) -> MovieDetailRead | None:
    movie = session.get(Movie, movie_id)
    if movie is None:
        return None
    assert movie.id is not None
    profile, target_languages = _profile_fields(session, movie)
    files = _media_file_reads(
        session,
        session.exec(select(MediaFile).where(MediaFile.movie_id == movie_id)).all(),
        target_languages,
        profile,
    )
    metadata = session.exec(select(MediaMetadata).where(MediaMetadata.movie_id == movie_id)).first()
    return MovieDetailRead(
        id=movie.id,
        title=movie.title,
        monitored=movie.monitored,
        status=movie.status,
        quality_profile_name=movie.quality_profile_name,
        genres=movie.genre_list,
        **metadata_fields(metadata),
        remote_path=movie.remote_path,
        language_profile_name=profile.name if profile else None,
        target_languages=target_languages,
        missing_subtitles_count=_missing_subtitles_count(files),
        files=files,
    )


def get_series_detail(session: Session, series_id: int) -> SeriesDetailRead | None:
    series = session.get(Series, series_id)
    if series is None:
        return None
    assert series.id is not None
    profile, target_languages = _profile_fields(session, series)
    media_files = session.exec(select(MediaFile).where(MediaFile.series_id == series_id)).all()
    files = _media_file_reads(session, media_files, target_languages, profile)
    files_by_path = {
        media_file.relative_path: file_read
        for media_file, file_read in zip(media_files, files, strict=True)
    }
    metadata = session.exec(
        select(MediaMetadata).where(MediaMetadata.series_id == series_id)
    ).first()
    pending_by_episode = _pending_languages_by_episode(session, series_id)
    episodes, episodes_unavailable = _episode_reads(
        session, series, files_by_path, pending_by_episode
    )
    return SeriesDetailRead(
        id=series.id,
        title=series.title,
        monitored=series.monitored,
        status=series.status,
        quality_profile_name=series.quality_profile_name,
        episode_count=series.episode_count,
        episode_file_count=series.episode_file_count,
        genres=series.genre_list,
        last_aired=series.last_aired,
        **metadata_fields(metadata),
        remote_path=series.remote_path,
        language_profile_name=profile.name if profile else None,
        target_languages=target_languages,
        missing_subtitles_count=_missing_subtitles_count(files),
        episodes=episodes,
        episodes_unavailable=episodes_unavailable,
    )


def _episode_reads(
    session: Session,
    series: Series,
    files_by_path: dict[str, MediaFileRead],
    pending_by_episode: dict[tuple[int, int], list[str]],
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
            pending_languages=pending_by_episode.get(
                (episode.season_number, episode.episode_number), []
            ),
        )
        for episode in episodes
    ], False


def _pending_languages_by_episode(
    session: Session, series_id: int
) -> dict[tuple[int, int], list[str]]:
    pending = session.exec(
        select(PendingSubtitle).where(PendingSubtitle.series_id == series_id)
    ).all()
    by_episode: dict[tuple[int, int], list[str]] = defaultdict(list)
    for row in pending:
        by_episode[(row.season_number, row.episode_number)].append(row.language)
    return by_episode


def _profile_fields(
    session: Session, item: Movie | Series
) -> tuple[LanguageProfile | None, list[str]]:
    profile = resolve_effective_profile(session, item)
    if profile is None:
        return None, []
    return profile, profile.target_language_list


def _media_file_reads(
    session: Session,
    media_files: Sequence[MediaFile],
    target_languages: list[str],
    profile: LanguageProfile | None,
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
    embedded_tracks_by_file_id: dict[int, list[EmbeddedTrack]] = defaultdict(list)
    for track in session.exec(
        select(EmbeddedTrack).where(col(EmbeddedTrack.media_file_id).in_(media_file_ids))
    ).all():
        embedded_tracks_by_file_id[track.media_file_id].append(track)
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
            if subtitle.origin == SubtitleOrigin.EMBEDDED:
                score = score_embedded_subtitle(subtitle, profile) if profile is not None else None
            else:
                score = acquired.score if acquired else None
            subtitle_reads.append(
                SubtitleRead(
                    id=subtitle.id,
                    language=subtitle.language,
                    origin=subtitle.origin.value,
                    size_bytes=subtitle.size_bytes,
                    track_index=subtitle.track_index,
                    provider=acquired.provider if acquired else None,
                    release_name=acquired.release_name if acquired else None,
                    score=score,
                    resolution_matched=attempt.resolution_matched if attempt else None,
                    source_matched=attempt.source_matched if attempt else None,
                    codec_matched=attempt.codec_matched if attempt else None,
                    release_group_matched=attempt.release_group_matched if attempt else None,
                    edition_matched=attempt.edition_matched if attempt else None,
                )
            )
        present = {subtitle.language for subtitle in subtitle_reads}
        subtitle_read_by_track_index = {
            subtitle_read.track_index: subtitle_read
            for subtitle_read in subtitle_reads
            if subtitle_read.origin == SubtitleOrigin.EMBEDDED.value
        }
        embedded_track_reads = [
            EmbeddedTrackRead(
                track_index=track.track_index,
                language=track.language,
                extracted=track.extracted,
                subtitle=subtitle_read_by_track_index.get(track.track_index),
            )
            for track in embedded_tracks_by_file_id.get(media_file.id, [])
        ]
        has_source_subtitle = profile is not None and any(
            language.lower() in present for language in profile.source_language_list
        )
        reads.append(
            MediaFileRead(
                id=media_file.id,
                relative_path=media_file.relative_path,
                size_bytes=media_file.size_bytes,
                subtitles=subtitle_reads,
                embedded_tracks=embedded_track_reads,
                missing_languages=[
                    language for language in target_languages if language.lower() not in present
                ],
                has_source_subtitle=has_source_subtitle,
            )
        )
    return reads


def _missing_subtitles_count(files: list[MediaFileRead]) -> int:
    """Files still missing at least one of the profile's target languages — each
    file's own `missing_languages` (computed in `_media_file_reads`) already answers
    that per file."""
    return sum(1 for file in files if file.missing_languages)
