from datetime import datetime

from sqlalchemy import Column, Enum, UniqueConstraint
from sqlmodel import Field, SQLModel

from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


class Subtitle(SQLModel, table=True):
    """A subtitle discovered for a `MediaFile`, persisted by the subtitle scan job.

    `relative_path` is stored relative to the media item's root folder, same
    convention as `MediaFile.relative_path`, so editing a connection's path mapping
    never invalidates rows. `forced`/`hearing_impaired` reflect the container's own
    disposition flags for an embedded track (`ROADMAP.md` 0.6.0); always `False` for an
    external subtitle, since that metadata isn't derivable from a bare filename.
    """

    __table_args__ = (UniqueConstraint("media_file_id", "relative_path"),)

    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", index=True, ondelete="CASCADE")
    language: str
    # values_callable persists the enum's lowercase `.value` ("external") instead of
    # SQLAlchemy's Enum default of `.name` ("EXTERNAL").
    origin: SubtitleOrigin = Field(
        sa_column=Column(
            Enum(SubtitleOrigin, values_callable=lambda enum: [member.value for member in enum]),
            nullable=False,
        )
    )
    relative_path: str
    track_index: int | None = None
    forced: bool = Field(default=False)
    hearing_impaired: bool = Field(default=False)
    # Byte size of the subtitle file itself (not the video) — recomputed on every scan
    # alongside `content_hash`, same source read. Works identically for external and
    # embedded subtitles since both end up as a real `.srt` sibling on disk by the time
    # `scan_media_subtitles` sees them (an embedded track is extracted first).
    size_bytes: int = Field(default=0)
    # sha256 of the subtitle file's bytes, recomputed on every scan (`scan_media_subtitles`) —
    # lets `translate_media_file` tell an unchanged source from one whose content changed
    # since the last translation.
    content_hash: str
    # Set by `translate_media_file` after it writes and rescans a translated output: the
    # source subtitle's `content_hash` at translation time. `None` for a subtitle that was
    # never produced by translation. A mismatch against the current source's `content_hash`
    # means the source changed and this target is stale.
    translated_from_hash: str | None = Field(default=None)
    scanned_at: datetime


class EmbeddedTrack(SQLModel, table=True):
    """Every subtitle track `ffprobe` detects inside a `MediaFile`'s container, persisted by
    the subtitle scan job regardless of whether it was actually extracted. `Subtitle` only
    gets a row for a track that was extracted into a real, usable file; this table is the
    full picture of what the container has, so the UI can show a track that was skipped —
    its language isn't one of the effective `LanguageProfile.source_languages`, its codec's
    extraction is toggled off (`extract_embedded_subtitles`/`ocr_embedded_subtitles`), or its
    language is already covered by an external subtitle — alongside the ones that were.

    Named `EmbeddedTrack`, not `EmbeddedSubtitleTrack`, to stay distinct from
    `probe_embedded_subtitles.EmbeddedSubtitleTrack` (one ffprobe stream, not persisted).
    """

    __table_args__ = (UniqueConstraint("media_file_id", "track_index"),)

    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(foreign_key="mediafile.id", index=True, ondelete="CASCADE")
    track_index: int
    codec_name: str
    language: str
    forced: bool = Field(default=False)
    hearing_impaired: bool = Field(default=False)
    # Whether this track resulted in a `Subtitle` row — `False` for one skipped by the
    # source-language gate, an already-covering external subtitle, or a disabled
    # extraction/OCR toggle.
    extracted: bool = Field(default=False)
    scanned_at: datetime


class SubtitleScanState(SQLModel, table=True):
    """Marks a `MediaFile` as having been probed by the subtitle scan at least once,
    and what it looked like at that time — the periodic fan-outs' readiness/re-probe
    signal.

    `subtitle_acquisition`/`subtitle_translation`'s fan-outs check for this row's
    existence before considering a file at all, so a file that hasn't been through
    subtitle discovery yet is never mistaken for one with nothing to acquire/translate.
    The subtitle scan fan-out itself re-probes a file once `probed_size_bytes` no
    longer matches `MediaFile.size_bytes` (the video was replaced) or `probed_at` is
    older than the configured recheck window (to still catch a manually-dropped
    external subtitle eventually) — see `subtitle_discovery.scan_eligibility`.
    """

    id: int | None = Field(default=None, primary_key=True)
    media_file_id: int = Field(
        foreign_key="mediafile.id", unique=True, index=True, ondelete="CASCADE"
    )
    probed_at: datetime
    probed_size_bytes: int
