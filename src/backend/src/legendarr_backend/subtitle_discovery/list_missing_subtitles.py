from collections import defaultdict

from sqlmodel import Session, col, select

from legendarr_backend.language_profiles.resolve_effective_profile import (
    resolve_effective_profile,
)
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_discovery.models import Subtitle


def list_media_files_without_subtitles(session: Session) -> list[MediaFile]:
    """`MediaFile` rows with no discovered subtitle at all, regardless of language.

    Language-profile-aware filtering (missing a specific target language) is a
    dashboard concern, not this function's — see `ROADMAP.md` 0.4.0.
    """
    return list(
        session.exec(
            select(MediaFile).where(~col(MediaFile.id).in_(select(Subtitle.media_file_id)))
        )
    )


def list_missing_target_languages_by_media_file(session: Session) -> dict[int, list[str]]:
    """For every `MediaFile` with an effective `LanguageProfile`, which of its profile's
    target languages have no discovered `Subtitle` yet — keyed by `media_file_id`, omitting
    files with nothing missing. A file with no effective profile is excluded too: there's
    nothing to measure "missing" against. Feeds the `/media/wanted` list and the movie/series
    detail pages' missing-subtitles count (`ROADMAP.md` 0.4.0).
    """
    media_files = list(session.exec(select(MediaFile)))
    if not media_files:
        return {}

    movie_ids = {file.movie_id for file in media_files if file.movie_id is not None}
    series_ids = {file.series_id for file in media_files if file.series_id is not None}
    movies_by_id = {
        movie.id: movie for movie in session.exec(select(Movie).where(col(Movie.id).in_(movie_ids)))
    }
    series_by_id = {
        series.id: series
        for series in session.exec(select(Series).where(col(Series.id).in_(series_ids)))
    }
    profile_by_movie_id = {
        movie_id: resolve_effective_profile(session, movie)
        for movie_id, movie in movies_by_id.items()
    }
    profile_by_series_id = {
        series_id: resolve_effective_profile(session, series)
        for series_id, series in series_by_id.items()
    }

    languages_by_file_id: dict[int, set[str]] = defaultdict(set)
    for subtitle in session.exec(
        select(Subtitle).where(col(Subtitle.media_file_id).in_([file.id for file in media_files]))
    ):
        languages_by_file_id[subtitle.media_file_id].add(subtitle.language)

    missing_by_file_id: dict[int, list[str]] = {}
    for file in media_files:
        assert file.id is not None
        profile = (
            profile_by_movie_id.get(file.movie_id)
            if file.movie_id is not None
            else profile_by_series_id.get(file.series_id)
        )
        if profile is None:
            continue
        present = languages_by_file_id.get(file.id, set())
        missing = [
            language for language in profile.target_language_list if language.lower() not in present
        ]
        if missing:
            missing_by_file_id[file.id] = missing
    return missing_by_file_id
