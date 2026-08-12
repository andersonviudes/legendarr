from legendarr_backend.subtitle_acquisition.opensubtitles_hash import (
    compute_opensubtitles_hash,
)


def test_compute_opensubtitles_hash_returns_none_below_chunk_size(tmp_path):
    video_path = tmp_path / "short.mkv"
    video_path.write_bytes(b"\x00" * 65535)

    assert compute_opensubtitles_hash(video_path) is None


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
