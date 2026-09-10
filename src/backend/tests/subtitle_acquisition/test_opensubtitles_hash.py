import time

from legendarr_backend.subtitle_acquisition import opensubtitles_hash as opensubtitles_hash_module
from legendarr_backend.subtitle_acquisition.opensubtitles_hash import (
    compute_opensubtitles_hash,
)


def test_compute_opensubtitles_hash_returns_none_below_chunk_size(tmp_path):
    video_path = tmp_path / "short.mkv"
    video_path.write_bytes(b"\x00" * 65535)

    assert compute_opensubtitles_hash(video_path) is None


def test_compute_opensubtitles_hash_returns_none_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.mkv"

    assert compute_opensubtitles_hash(missing_path) is None


def test_compute_opensubtitles_hash_matches_known_value_for_uniform_content(tmp_path):
    # 64KB of zero bytes: checksum starts at the file size (0x10000) and every 8-byte
    # word from both the (identical, overlapping) first/last chunks contributes 0.
    video_path = tmp_path / "zeroes.mkv"
    video_path.write_bytes(b"\x00" * 65536)

    assert compute_opensubtitles_hash(video_path) == "0000000000010000"


def test_compute_opensubtitles_hash_reads_first_and_last_chunk_separately(tmp_path):
    # 128KB with a distinct first half and second half: proves the hash isn't just a
    # function of one end of the file.
    video_path = tmp_path / "mixed.mkv"
    video_path.write_bytes((b"\x00" * 65536) + (b"\x01" * 65536))

    assert compute_opensubtitles_hash(video_path) == "2020202020222000"


def test_compute_opensubtitles_hash_differs_for_different_content(tmp_path):
    zeroes_path = tmp_path / "zeroes.mkv"
    zeroes_path.write_bytes(b"\x00" * 65536)
    ones_path = tmp_path / "ones.mkv"
    ones_path.write_bytes(b"\xff" * 65536)

    assert compute_opensubtitles_hash(zeroes_path) != compute_opensubtitles_hash(ones_path)


def test_compute_opensubtitles_hash_gives_up_after_timeout(monkeypatch, tmp_path):
    video_path = tmp_path / "movie.mkv"
    video_path.write_bytes(b"\x00" * 65536)

    def _stalled_compute_hash(path):
        time.sleep(2)
        return "deadbeef"

    monkeypatch.setattr(opensubtitles_hash_module, "_compute_hash", _stalled_compute_hash)

    started = time.monotonic()
    result = compute_opensubtitles_hash(video_path, timeout_seconds=0.05)
    elapsed = time.monotonic() - started

    # Regression check for the hang this guards against: a stalled read (e.g. a stuck
    # network mount) must not block the caller past `timeout_seconds`, mirroring
    # `transcribe_audio`'s equivalent regression test.
    assert elapsed < 1.0
    assert result is None
