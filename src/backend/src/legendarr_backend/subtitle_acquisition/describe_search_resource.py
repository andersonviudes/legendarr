import re
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from legendarr_backend.media_library.models import MediaFile
from legendarr_backend.subtitle_acquisition.candidate_evaluation.release_attributes import (
    extract_release_attributes,
)
from legendarr_backend.subtitle_acquisition.search_context import resolve_subtitle_search_context

# A separate, display-only vocabulary — release_attributes.py stays scoped to the five
# attributes match_score.py weights (see its own docstring), so audio/HDR/release-group
# detection for this info-only preview lives here instead, where a looser or wrong
# guess can't skew candidate scoring.
_AUDIO_CODEC_ALIASES = {
    "eac3": "DDP",
    "ddp": "DDP",
    "ac3": "AC3",
    "truehd": "TrueHD",
    "dtshd": "DTS-HD",
    "dts": "DTS",
    "aac": "AAC",
    "flac": "FLAC",
    "opus": "Opus",
    "mp3": "MP3",
}
_AUDIO_CODEC_PATTERN = re.compile(
    r"\b(e-?ac3|ddp|ac3|truehd|dts-hd|dts|aac|flac|opus|mp3)\b", re.IGNORECASE
)
_AUDIO_CHANNELS_PATTERN = re.compile(r"\b(\d\.\d)\b")
_HDR_PATTERN = re.compile(r"\b(hdr10\+|hdr10|hdr)\b", re.IGNORECASE)
_DV_PATTERN = re.compile(r"\b(dv|dolby\s?vision)\b", re.IGNORECASE)

# Unlike release_attributes.py's own group pattern (anchored right after the last
# *recognized* vocabulary token, so a bracket tag it doesn't know about — a streaming
# service, an HDR flag — breaks the anchor), this just takes the last dash-prefixed
# token before the extension. Looser, but release groups reliably sit right there
# regardless of what other tags come before them.
_GROUP_PATTERN = re.compile(r"-([A-Za-z0-9]{2,15})$")


@dataclass(frozen=True)
class SubtitleSearchResource:
    """What the manual-search panel's "Resource" info box shows: the video's on-disk
    path, and a scene-style release name reconstructed from it. Display-only — a
    best-effort preview built from whatever quality tags survived Sonarr/Radarr's own
    renaming, not the literal text sent to providers (`search_media_file_subtitle_candidates`
    searches by title) and not guaranteed to match a candidate's real release name —
    a tag Sonarr's renamer dropped (streaming service, exact video codec) simply isn't
    recoverable from the local filename anymore.
    """

    path: str
    release_name: str


def describe_subtitle_search_resource(
    session: Session, media_file: MediaFile, video_path: Path
) -> SubtitleSearchResource:
    """Reassemble `video_path`'s filename into a dotted, scene-style release name —
    title, season/episode, then whichever of resolution/source/audio/HDR/DV/codec were
    recognized in the filename, in that fixed order. Season/episode come from `context`
    (the DB-resolved episode) rather than the filename's own guess, since it's the
    authoritative one and always available for a series file even when the filename
    doesn't spell out an `SxxEyy` tag.
    """
    context = resolve_subtitle_search_context(session, media_file, video_path)
    stem = video_path.stem
    attributes = extract_release_attributes(stem)
    parts = [context.title.replace(" ", ".")]
    if context.season_number is not None and context.episode_number is not None:
        parts.append(f"S{context.season_number:02d}E{context.episode_number:02d}")
    if attributes.resolution is not None:
        parts.append(attributes.resolution)
    if attributes.source is not None:
        parts.append(attributes.source.upper())
    audio = _describe_audio(stem)
    if audio is not None:
        parts.append(audio)
    if _HDR_PATTERN.search(stem):
        parts.append("HDR")
    if _DV_PATTERN.search(stem):
        parts.append("DV")
    if attributes.codec is not None:
        parts.append(attributes.codec.upper())
    release_name = ".".join(parts)
    group_match = _GROUP_PATTERN.search(stem)
    if group_match is not None:
        release_name = f"{release_name}-{group_match.group(1)}"
    return SubtitleSearchResource(path=str(video_path), release_name=release_name)


def _describe_audio(stem: str) -> str | None:
    """`"DDP5.1"`-style audio tag, codec plus channel layout run together with no
    separator (scene convention) — `None` if `stem` names no recognized audio codec.
    The channel layout is searched independently of the codec match (not required to
    sit next to it) since a bracket tag like `[EAC3 Atmos 5.1]` has other words
    between them.
    """
    codec_match = _AUDIO_CODEC_PATTERN.search(stem)
    if codec_match is None:
        return None
    codec_key = codec_match.group(1).lower().replace("-", "")
    codec = _AUDIO_CODEC_ALIASES[codec_key]
    channels_match = _AUDIO_CHANNELS_PATTERN.search(stem)
    if channels_match is None:
        return codec
    return f"{codec}{channels_match.group(1)}"
