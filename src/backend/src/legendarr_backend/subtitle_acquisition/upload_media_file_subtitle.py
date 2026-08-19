from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file

# Same set `subtitle_discovery.scan_video_subtitles` already recognizes as an external
# sidecar file — a manual upload has to land in a format the scan will actually pick
# back up, so this mirrors that allowlist rather than inventing a separate one.
ALLOWED_UPLOAD_SUFFIXES = {".srt", ".ass", ".ssa", ".vtt"}


def upload_subtitle_for_media_file(
    session: Session,
    media_file: MediaFile,
    video_path: Path,
    language: str,
    filename: str,
    content: bytes,
) -> tuple[bool, str]:
    """Save a user-uploaded subtitle file next to `video_path`, as an external sidecar
    in `language`, then rescan so it shows up as a normal `Subtitle` row.

    Rejects a file whose extension isn't in `ALLOWED_UPLOAD_SUFFIXES` without writing
    anything — same tolerant `(False, message)` shape `download_subtitle_candidate`
    uses, so the web layer can show it inline instead of a 500.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        return False, f"Unsupported file type '{suffix or filename}'"

    output_path = video_path.with_name(f"{video_path.stem}.{language.lower()}{suffix}")
    output_path.write_bytes(content)
    scan_subtitles_for_media_file(session, media_file, video_path)
    return True, f"Uploaded {language} subtitle"
