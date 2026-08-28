import re

from sqlmodel import Session, select

from legendarr_backend.config.settings import get_settings
from legendarr_backend.media_library.models import Movie, Series

# `{kind}_{id}.jpg` — matches what `fetch_metadata._cache_poster` writes.
_POSTER_FILENAME_RE = re.compile(r"^(movie|series)_(\d+)\.jpg$")


def cleanup_orphaned_posters(session: Session) -> int:
    """Delete cached poster files under `Settings.poster_cache_dir` whose movie/series
    no longer exists.

    This is the only way a `{kind}_{id}.jpg` file goes orphaned — a metadata refetch
    overwrites the same file in place instead of writing a new one (see
    `fetch_metadata._cache_poster`), so a stale file only lingers once the item itself
    has left the library. Returns how many files were removed.
    """
    posters_dir = get_settings().poster_cache_dir
    if not posters_dir.is_dir():
        return 0
    movie_ids = set(session.exec(select(Movie.id)).all())
    series_ids = set(session.exec(select(Series.id)).all())
    removed = 0
    for path in posters_dir.iterdir():
        match = _POSTER_FILENAME_RE.match(path.name)
        if match is None:
            continue
        kind, media_id = match.group(1), int(match.group(2))
        live_ids = movie_ids if kind == "movie" else series_ids
        if media_id not in live_ids:
            path.unlink()
            removed += 1
    return removed
