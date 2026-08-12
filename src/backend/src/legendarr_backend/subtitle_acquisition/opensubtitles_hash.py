"""OpenSubtitles' own "moviehash" algorithm: a 64-bit checksum derived from a file's
size plus its first and last 64KB, used by `use_hash` search (see
`subtitle_acquisition/providers/opensubtitles.py`) instead of a plain title query.
"""

import struct
from pathlib import Path
from typing import BinaryIO

_CHUNK_SIZE = 65536
_LONGLONG_SIZE = 8
_MASK_64_BIT = 0xFFFFFFFFFFFFFFFF


def compute_opensubtitles_hash(path: Path) -> str | None:
    """Hex-encoded OpenSubtitles hash for the video at `path`, or `None` if it's
    smaller than the 64KB the algorithm reads from each end — callers just fall back
    to a plain query in that case, same as when hashing isn't requested at all.
    """
    file_size = path.stat().st_size
    if file_size < _CHUNK_SIZE:
        return None

    checksum = file_size
    with path.open("rb") as file:
        checksum = _accumulate_chunk(file, checksum)
        file.seek(file_size - _CHUNK_SIZE)
        checksum = _accumulate_chunk(file, checksum)
    return f"{checksum:016x}"


def _accumulate_chunk(file: BinaryIO, checksum: int) -> int:
    for _ in range(_CHUNK_SIZE // _LONGLONG_SIZE):
        (value,) = struct.unpack("<q", file.read(_LONGLONG_SIZE))
        checksum = (checksum + value) & _MASK_64_BIT
    return checksum
