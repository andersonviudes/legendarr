from legendarr_backend.subtitle_discovery.pgs_format import parse_pgs

# PGS segment types (BD-spec) — used to hand-build minimal valid `.sup` byte sequences.
_PCS = 0x16
_WDS = 0x17
_PDS = 0x14
_ODS = 0x15
_END = 0x80


def _segment(pts_ticks: int, segment_type: int, payload: bytes) -> bytes:
    return (
        b"PG"
        + pts_ticks.to_bytes(4, "big")
        + (0).to_bytes(4, "big")  # DTS, unused
        + bytes([segment_type])
        + len(payload).to_bytes(2, "big")
        + payload
    )


def _pcs(object_count: int, composition_state: int = 0x80) -> bytes:
    payload = (
        (1920).to_bytes(2, "big")  # video width
        + (1080).to_bytes(2, "big")  # video height
        + bytes([0x10])  # frame rate
        + (0).to_bytes(2, "big")  # composition number
        + bytes([composition_state])
        + bytes([0])  # palette update flag
        + bytes([0])  # palette id
        + bytes([object_count])
    )
    for object_id in range(object_count):
        payload += (
            object_id.to_bytes(2, "big")
            + bytes([0])  # window id
            + bytes([0])  # object cropped flag
            + (0).to_bytes(2, "big")  # horizontal position
            + (0).to_bytes(2, "big")  # vertical position
        )
    return payload


def _pds(entries: dict[int, tuple[int, int, int, int]]) -> bytes:
    payload = bytes([0, 0])  # palette id, version
    for entry_id, (y, cr, cb, alpha) in entries.items():
        payload += bytes([entry_id, y, cr, cb, alpha])
    return payload


def _ods(width: int, height: int, rle: bytes) -> bytes:
    object_data_length = 4 + len(rle)
    return (
        (0).to_bytes(2, "big")  # object id
        + bytes([0])  # object version number
        + bytes([0xC0])  # first + last in sequence
        + object_data_length.to_bytes(3, "big")
        + width.to_bytes(2, "big")
        + height.to_bytes(2, "big")
        + rle
    )


def _two_pixel_row(color_index: int) -> bytes:
    """RLE for a 2x1 bitmap: two pixels of `color_index`, then end-of-line."""
    return bytes([color_index, color_index, 0x00, 0x00])


_BLACK_OPAQUE = (0, 128, 128, 255)  # Y=0 Cr=128 Cb=128 alpha=255 -> RGB (0, 0, 0)
_WHITE_OPAQUE = (255, 128, 128, 255)  # Y=255 Cr=128 Cb=128 alpha=255 -> RGB (255, 255, 255)


def test_parse_pgs_decodes_a_single_cue_start_and_end():
    palette = _pds({1: _BLACK_OPAQUE})
    data = (
        _segment(0, _PCS, _pcs(object_count=1))
        + _segment(0, _PDS, palette)
        + _segment(0, _ODS, _ods(2, 1, _two_pixel_row(1)))
        + _segment(0, _END, b"")
        + _segment(90_000, _PCS, _pcs(object_count=0, composition_state=0x00))
        + _segment(90_000, _END, b"")
    )

    cues = parse_pgs(data)

    assert len(cues) == 1
    cue = cues[0]
    assert (cue.start_ms, cue.end_ms) == (0, 1000)
    assert cue.image.size == (2, 1)
    assert cue.image.getpixel((0, 0)) == (0, 0, 0, 255)
    assert cue.image.getpixel((1, 0)) == (0, 0, 0, 255)


def test_parse_pgs_closes_previous_cue_when_next_display_set_is_also_visible():
    """Back-to-back visible Display Sets (no empty one in between) still close the first
    cue — at the second one's timestamp — instead of merging them."""
    palette = _pds({1: _BLACK_OPAQUE, 2: _WHITE_OPAQUE})
    data = (
        _segment(0, _PCS, _pcs(object_count=1))
        + _segment(0, _PDS, palette)
        + _segment(0, _ODS, _ods(2, 1, _two_pixel_row(1)))
        + _segment(0, _END, b"")
        + _segment(90_000, _PCS, _pcs(object_count=1))
        + _segment(90_000, _PDS, palette)
        + _segment(90_000, _ODS, _ods(2, 1, _two_pixel_row(2)))
        + _segment(90_000, _END, b"")
        + _segment(180_000, _PCS, _pcs(object_count=0, composition_state=0x00))
        + _segment(180_000, _END, b"")
    )

    cues = parse_pgs(data)

    assert [(c.start_ms, c.end_ms) for c in cues] == [(0, 1000), (1000, 2000)]
    assert cues[0].image.getpixel((0, 0)) == (0, 0, 0, 255)
    assert cues[1].image.getpixel((0, 0)) == (255, 255, 255, 255)


def test_parse_pgs_decodes_colored_and_colorless_long_runs():
    """A wider bitmap exercising all four RLE run kinds: colored short (>1 pixel run of a
    palette color), colorless short/long (transparent runs, using color index 0), and a
    colored long run (>63 pixels)."""
    palette = _pds({1: _BLACK_OPAQUE})
    # 3 colored pixels (colored short, length=3, color=1), then 70 transparent pixels
    # (colorless long run, length=70), then end of line.
    rle = bytes([0x00, 0x80 | 0x03, 0x01]) + bytes([0x00, 0x40, 70]) + bytes([0x00, 0x00])
    data = (
        _segment(0, _PCS, _pcs(object_count=1))
        + _segment(0, _PDS, palette)
        + _segment(0, _ODS, _ods(73, 1, rle))
        + _segment(0, _END, b"")
        + _segment(90_000, _PCS, _pcs(object_count=0, composition_state=0x00))
        + _segment(90_000, _END, b"")
    )

    cues = parse_pgs(data)

    assert len(cues) == 1
    image = cues[0].image
    assert image.size == (73, 1)
    for x in range(3):
        assert image.getpixel((x, 0)) == (0, 0, 0, 255)
    for x in range(3, 73):
        assert image.getpixel((x, 0)) == (0, 0, 0, 0)


def test_parse_pgs_drops_a_cue_left_open_at_end_of_stream():
    """A truncated stream — the closing empty Display Set never arrives — drops the still-
    open cue instead of guessing at an end time."""
    palette = _pds({1: _BLACK_OPAQUE})
    data = (
        _segment(0, _PCS, _pcs(object_count=1))
        + _segment(0, _PDS, palette)
        + _segment(0, _ODS, _ods(2, 1, _two_pixel_row(1)))
        + _segment(0, _END, b"")
    )

    cues = parse_pgs(data)

    assert cues == []


def test_parse_pgs_stops_gracefully_on_truncated_segment():
    palette = _pds({1: _BLACK_OPAQUE})
    good = (
        _segment(0, _PCS, _pcs(object_count=1))
        + _segment(0, _PDS, palette)
        + _segment(0, _ODS, _ods(2, 1, _two_pixel_row(1)))
        + _segment(0, _END, b"")
        + _segment(90_000, _PCS, _pcs(object_count=0, composition_state=0x00))
        + _segment(90_000, _END, b"")
    )
    truncated = good + b"PG" + (200_000).to_bytes(4, "big") + (0).to_bytes(4, "big") + bytes([_PCS])
    truncated += (50).to_bytes(2, "big")  # claims a 50-byte payload that was never written

    cues = parse_pgs(truncated)

    assert [(c.start_ms, c.end_ms) for c in cues] == [(0, 1000)]


def test_parse_pgs_returns_empty_list_for_data_with_bad_magic():
    assert parse_pgs(b"not a pgs stream at all") == []


def test_parse_pgs_returns_empty_list_for_empty_input():
    assert parse_pgs(b"") == []
