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
    scanned_at: datetime
