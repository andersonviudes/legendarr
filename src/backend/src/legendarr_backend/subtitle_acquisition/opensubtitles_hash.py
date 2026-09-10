"""OpenSubtitles' own "moviehash" algorithm: a 64-bit checksum derived from a file's
size plus its first and last 64KB, used by `use_hash` search (see
`subtitle_acquisition/providers/opensubtitles.py`) instead of a plain title query.
"""

import logging
import struct
import threading
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536
_LONGLONG_SIZE = 8
_MASK_64_BIT = 0xFFFFFFFFFFFFFFFF

# Generous bound for reading 128KB off local disk — only meant to catch a stalled
# network mount, not a slow-but-working one.
DEFAULT_HASH_TIMEOUT_SECONDS = 30.0


def compute_opensubtitles_hash(
    path: Path, *, timeout_seconds: float = DEFAULT_HASH_TIMEOUT_SECONDS
) -> str | None:
    """Hex-encoded OpenSubtitles hash for the video at `path`, or `None` for any of:
    `path` doesn't exist, it's smaller than the 64KB the algorithm reads from each end,
    or reading it took longer than `timeout_seconds` — callers just fall back to a plain
    query in any of those cases, same as when hashing isn't requested at all.

    Runs `_compute_hash` on a daemon thread and gives up waiting after `timeout_seconds`,
    same `Thread`-not-`ThreadPoolExecutor` shape as `subtitle_acquisition.
    audio_transcription.transcribe_audio.transcribe_audio_track` (see its docstring for
    why) — a video file on a stalled network mount blocks the underlying `stat()`/
    `read()` syscalls themselves, which no Python-level timeout can interrupt, so this
    only stops the call from wedging its caller's worker forever, not the blocked read
    itself.
    """
    result: list[str | None] = []

    def _target() -> None:
        try:
            result.append(_compute_hash(path))
        except OSError:
            logger.warning("opensubtitles hash computation failed for %s", path, exc_info=True)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if not result:
        if thread.is_alive():
            logger.warning(
                "opensubtitles hash computation for %s timed out after %.0fs",
                path,
                timeout_seconds,
            )
        return None
    return result[0]


def _compute_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
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
