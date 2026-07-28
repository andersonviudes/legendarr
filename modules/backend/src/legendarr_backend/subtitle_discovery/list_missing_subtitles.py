from sqlmodel import Session, select

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.models import Subtitle


def list_media_files_without_subtitles(session: Session) -> list[MediaFile]:
    """`MediaFile` rows with no discovered subtitle at all, regardless of language.

    Language-profile-aware filtering (missing a specific target language) is a
    dashboard concern, not this function's — see `ROADMAP.md` 0.4.0.
    """
    return list(
        session.exec(select(MediaFile).where(~MediaFile.id.in_(select(Subtitle.media_file_id))))
    )
