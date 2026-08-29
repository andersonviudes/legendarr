import logging
from typing import cast

from sqlmodel import Session, select

from legendarr_backend.arr_clients.base import SeriesLibraryClient
from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.media_library.locate import resolve_media_file_path
from legendarr_backend.media_library.models import MediaFile, Series
from legendarr_backend.subtitle_acquisition.candidate_evaluation.match_score import (
    evaluate_candidate,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

logger = logging.getLogger(__name__)


def reconcile_pending_subtitles_for_series(session: Session, series_id: int) -> int:
    """Move every `PendingSubtitle` of `series_id` onto disk, for whichever ones now
    have a matching `MediaFile` — called after a "Scan Disk"/webhook-triggered scan
    cascades for this series, so a subtitle acquired before an episode was downloaded
    shows up as a normal external `Subtitle` once it is.

    A single live Sonarr `list_episodes` call maps season/episode number to
    `relative_path` for the whole series at once (cheaper than resolving each pending
    row's episode individually), skipped entirely — no Sonarr call at all — when the
    series has no pending subtitles, the common case. Returns how many were
    materialized; never raises (same skip-don't-fail treatment as
    `resolve_media_file_episode` for a connection that no longer exists or can't be
    reached — the rows are simply left pending for the next scan to retry).
    """
    pending_rows = list(
        session.exec(select(PendingSubtitle).where(PendingSubtitle.series_id == series_id))
    )
    if not pending_rows:
        return 0

    series = session.get(Series, series_id)
    if series is None:
        return 0
    arr_service = session.get(ArrService, series.arr_service_id)
    if arr_service is None:
        return 0
    client = build_client(arr_service)
    sonarr_client = cast(SeriesLibraryClient, client)
    try:
        episodes = sonarr_client.list_episodes(series.arr_id)
    except ProviderClientError:
        logger.warning(
            "pending-subtitle reconcile skipped: couldn't reach Sonarr for %r", series.title
        )
        return 0
    finally:
        client.close()

    relative_path_by_episode = {
        (episode.season_number, episode.episode_number): episode.relative_path
        for episode in episodes
        if episode.relative_path
    }

    materialized = 0
    for pending in pending_rows:
        relative_path = relative_path_by_episode.get(
            (pending.season_number, pending.episode_number)
        )
        if relative_path is None:
            continue
        media_file = session.exec(
            select(MediaFile).where(
                MediaFile.series_id == series_id, MediaFile.relative_path == relative_path
            )
        ).first()
        if media_file is None:
            continue
        video_path = resolve_media_file_path(session, media_file)
        if video_path is None or not video_path.is_file():
            continue

        assert media_file.id is not None
        suffix = pending.filename.rsplit(".", 1)[-1]
        output_path = video_path.with_name(f"{video_path.stem}.{pending.language.lower()}.{suffix}")
        output_path.write_bytes(pending.content)
        scan_subtitles_for_media_file(session, media_file, video_path)
        if pending.provider is not None and pending.download_id is not None:
            result = SubtitleSearchResult(
                release_name=pending.release_name or pending.filename,
                download_id=pending.download_id,
                language=pending.language,
                page_link=None,
            )
            record_acquired_subtitle(
                session,
                media_file.id,
                pending.language,
                provider=pending.provider,
                release_name=result.release_name,
                download_id=pending.download_id,
                evaluation=evaluate_candidate(result, video_path.stem),
            )
        session.delete(pending)
        materialized += 1
        logger.info(
            "materialized pending %s subtitle for %r S%02dE%02d",
            pending.language,
            series.title,
            pending.season_number,
            pending.episode_number,
        )

    return materialized
