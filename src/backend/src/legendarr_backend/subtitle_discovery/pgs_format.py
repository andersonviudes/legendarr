"""Parser for the PGS ("Presentation Graphic Stream") bitmap subtitle format used by
Blu-ray discs — the raw `.sup` bytes `probe_embedded_subtitles.extract_pgs_subtitle_stream`
dumps from an `hdmv_pgs_subtitle` container track (ROADMAP.md 0.14.0).

A `.sup` stream is a sequence of segments (PCS/WDS/PDS/ODS/END), grouped into "Display
Sets" that each start with a Presentation Composition Segment (PCS). A Display Set with
one or more composition objects shows a subtitle bitmap; an empty one (0 objects) hides
whatever was showing. This module decodes that into `PgsSubtitleCue`s — a start/end
timestamp plus the composited bitmap as an RGBA `PIL.Image` — pure parsing/decoding only,
mirroring `subtitle_format.py`'s "raw bytes <-> structured data" role. OCR itself happens
in `ocr_embedded_subtitles.py`.
"""

import logging
from dataclasses import dataclass, field

from PIL import Image

logger = logging.getLogger(__name__)

_MAGIC = b"PG"
_SEGMENT_HEADER_SIZE = 13  # 2 (magic) + 4 (PTS) + 4 (DTS) + 1 (type) + 2 (size)

_TYPE_PDS = 0x14
_TYPE_ODS = 0x15
_TYPE_PCS = 0x16
_TYPE_WDS = 0x17
_TYPE_END = 0x80

_TRANSPARENT = (0, 0, 0, 0)


@dataclass(frozen=True)
class PgsSubtitleCue:
    start_ms: int
    end_ms: int
    image: Image.Image


@dataclass(frozen=True)
class _Segment:
    type: int
    pts_ms: int
    payload: bytes


@dataclass
class _DisplaySet:
    pts_ms: int
    object_count: int
    pds_payloads: list[bytes] = field(default_factory=list)
    ods_payloads: list[bytes] = field(default_factory=list)


def parse_pgs(data: bytes) -> list[PgsSubtitleCue]:
    """Decode a `.sup` byte stream into subtitle cues, in presentation order.

    A truncated or malformed stream degrades gracefully: segment iteration stops at the
    first bad/incomplete segment header instead of raising, and a cue left open at end of
    stream (no closing empty Display Set ever arrived) is dropped rather than guessed at.
    """
    cues: list[PgsSubtitleCue] = []
    open_start_ms: int | None = None
    open_image: Image.Image | None = None

    for display_set in _iter_display_sets(_iter_segments(data)):
        image = None
        if display_set.object_count > 0 and display_set.ods_payloads:
            palette = _build_palette(display_set.pds_payloads)
            image = _decode_object(display_set.ods_payloads, palette)

        if open_start_ms is not None:
            # open_image is always set alongside open_start_ms, just below.
            assert open_image is not None
            cues.append(PgsSubtitleCue(open_start_ms, display_set.pts_ms, open_image))
            open_start_ms = None
            open_image = None

        if image is not None:
            open_start_ms = display_set.pts_ms
            open_image = image

    return cues


def _iter_segments(data: bytes):
    offset = 0
    length = len(data)
    while offset + _SEGMENT_HEADER_SIZE <= length:
        if data[offset : offset + 2] != _MAGIC:
            logger.warning("PGS parsing stopped: bad segment magic at offset %d", offset)
            return
        pts_ticks = int.from_bytes(data[offset + 2 : offset + 6], "big")
        segment_type = data[offset + 10]
        size = int.from_bytes(data[offset + 11 : offset + 13], "big")
        payload_start = offset + _SEGMENT_HEADER_SIZE
        payload_end = payload_start + size
        if payload_end > length:
            logger.warning("PGS parsing stopped: truncated segment at offset %d", offset)
            return
        # PTS is a 90 kHz clock, same convention `probe_embedded_subtitles` doesn't need
        # since ffprobe/ffmpeg timestamps are handled for it — converted to ms here instead.
        yield _Segment(
            type=segment_type, pts_ms=pts_ticks // 90, payload=data[payload_start:payload_end]
        )
        offset = payload_end


def _iter_display_sets(segments):
    """Group segments into Display Sets, each anchored on a PCS. Segments arriving before
    the first PCS (shouldn't happen in a valid stream) are dropped; `END` segments carry no
    useful payload — a Display Set's boundary is the next PCS or end of stream."""
    current: _DisplaySet | None = None
    for segment in segments:
        if segment.type == _TYPE_PCS:
            if current is not None:
                yield current
            current = _DisplaySet(
                pts_ms=segment.pts_ms, object_count=_pcs_object_count(segment.payload)
            )
        elif current is None or segment.type == _TYPE_END:
            continue
        elif segment.type == _TYPE_PDS:
            current.pds_payloads.append(segment.payload)
        elif segment.type == _TYPE_ODS:
            current.ods_payloads.append(segment.payload)
    if current is not None:
        yield current


def _pcs_object_count(payload: bytes) -> int:
    # width(2) height(2) frame_rate(1) composition_number(2) composition_state(1)
    # palette_update_flag(1) palette_id(1) object_count(1) -> object_count at offset 10.
    return payload[10] if len(payload) > 10 else 0


def _build_palette(pds_payloads: list[bytes]) -> dict[int, tuple[int, int, int, int]]:
    palette: dict[int, tuple[int, int, int, int]] = {}
    for payload in pds_payloads:
        entries = payload[2:]  # palette_id(1) + version(1), then 5-byte entries
        usable_length = (len(entries) // 5) * 5
        for offset in range(0, usable_length, 5):
            entry_id, y, cr, cb, alpha = entries[offset : offset + 5]
            palette[entry_id] = _ycbcr_to_rgba(y, cr, cb, alpha)
    return palette


def _ycbcr_to_rgba(y: int, cr: int, cb: int, alpha: int) -> tuple[int, int, int, int]:
    # BT.601 full-range YCbCr -> RGB, the convention PGS palette entries use.
    r = y + 1.402 * (cr - 128)
    g = y - 0.344136 * (cb - 128) - 0.714136 * (cr - 128)
    b = y + 1.772 * (cb - 128)
    return (_clamp_byte(r), _clamp_byte(g), _clamp_byte(b), alpha)


def _clamp_byte(value: float) -> int:
    return max(0, min(255, round(value)))


def _decode_object(
    ods_payloads: list[bytes], palette: dict[int, tuple[int, int, int, int]]
) -> Image.Image | None:
    """Reassemble one object's RLE bitmap data, possibly split across several ODS segments
    (`last_in_sequence_flag` distinguishes the first segment, which carries the width/height
    header, from continuation segments, which are pure RLE data)."""
    width = height = 0
    rle = bytearray()
    for payload in ods_payloads:
        if len(payload) < 4:
            continue
        is_first = bool(payload[3] & 0x40)
        if is_first:
            if len(payload) < 11:
                continue
            width = int.from_bytes(payload[7:9], "big")
            height = int.from_bytes(payload[9:11], "big")
            rle += payload[11:]
        else:
            rle += payload[4:]
    if width == 0 or height == 0:
        return None
    return _rle_to_image(bytes(rle), width, height, palette)


def _rle_to_image(
    rle: bytes, width: int, height: int, palette: dict[int, tuple[int, int, int, int]]
) -> Image.Image:
    """Decode PGS's 2-color-plane RLE encoding into an RGBA pixel buffer.

    Each run is either a single non-zero byte (one pixel of that palette color) or a
    `0x00`-prefixed run: colorless/colored, short/long, per the two high bits of the
    second byte — see the four branches below.
    """
    pixels = bytearray(width * height * 4)
    x = y = 0
    index = 0
    length = len(rle)
    while index < length and y < height:
        first = rle[index]
        index += 1
        if first != 0:
            _set_pixel(pixels, width, x, y, palette.get(first, _TRANSPARENT))
            x += 1
            continue
        if index >= length:
            break
        second = rle[index]
        index += 1
        if second == 0:
            x, y = 0, y + 1
            continue
        run_flags = second & 0xC0
        run_length_high = second & 0x3F
        if run_flags == 0x00:
            run_length, color_index = run_length_high, 0
        elif run_flags == 0x40:
            if index >= length:
                break
            run_length, color_index = (run_length_high << 8) | rle[index], 0
            index += 1
        elif run_flags == 0x80:
            if index >= length:
                break
            run_length, color_index = run_length_high, rle[index]
            index += 1
        else:
            if index + 1 >= length:
                break
            run_length = (run_length_high << 8) | rle[index]
            color_index = rle[index + 1]
            index += 2
        color = palette.get(color_index, _TRANSPARENT)
        for _ in range(run_length):
            if x >= width:
                break
            _set_pixel(pixels, width, x, y, color)
            x += 1
    return Image.frombytes("RGBA", (width, height), bytes(pixels))


def _set_pixel(
    buffer: bytearray, width: int, x: int, y: int, color: tuple[int, int, int, int]
) -> None:
    offset = (y * width + x) * 4
    buffer[offset : offset + 4] = bytes(color)
