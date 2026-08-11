from sqlmodel import Session, select

from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.locate import resolve_media_file_owner
from legendarr_backend.media_library.models import MediaFile, Movie, Series


def resolve_effective_profile(session: Session, item: Movie | Series) -> LanguageProfile | None:
    """The `LanguageProfile` that applies to a `Movie`/`Series`: its own override
    (`language_profile_id`) when set, otherwise whichever profile is marked
    `is_default`. Shared by the translation orchestrator and anywhere else that needs
    to show or act on a media item's effective profile."""
    if item.language_profile_id is not None:
        return session.get(LanguageProfile, item.language_profile_id)
    return session.exec(select(LanguageProfile).where(LanguageProfile.is_default)).first()


def resolve_media_file_profile(session: Session, media_file: MediaFile) -> LanguageProfile | None:
    """Same as `resolve_effective_profile`, but starting from a `MediaFile` instead of its
    `Movie`/`Series` owner — shared by `subtitle_translation` and `subtitle_discovery` so
    both slices resolve a file's effective profile the same way."""
    item = resolve_media_file_owner(session, media_file)
    if item is None:
        return None
    return resolve_effective_profile(session, item)
