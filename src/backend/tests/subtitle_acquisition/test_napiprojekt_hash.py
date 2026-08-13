import hashlib

from legendarr_backend.subtitle_acquisition.napiprojekt_hash import (
    compute_napiprojekt_hash,
    napiprojekt_subhash,
)


def test_compute_napiprojekt_hash_matches_md5_for_a_file_under_10mb(tmp_path):
    video_path = tmp_path / "short.mkv"
    video_path.write_bytes(b"\x00" * 1024)

    assert compute_napiprojekt_hash(video_path) == hashlib.md5(b"\x00" * 1024).hexdigest()


def test_compute_napiprojekt_hash_only_reads_the_first_10mb(tmp_path):
    ten_mb = 1024 * 1024 * 10
    video_path = tmp_path / "large.mkv"
    video_path.write_bytes((b"\x00" * ten_mb) + (b"\xff" * 1024))

    assert compute_napiprojekt_hash(video_path) == hashlib.md5(b"\x00" * ten_mb).hexdigest()


def test_napiprojekt_subhash_matches_known_value():
    # Real hash/subhash pairs confirmed against Bazarr's own recorded cassette
    # (`/home/viudes/projects/bazarr/tests/subliminal_patch/cassettes/test_napiprojekt/
    # test_list_subtitles_movie.yaml`), not derived from this port itself.
    assert napiprojekt_subhash("444563eef63f83d47cabb888f7a45113") == "a6f09"
    assert napiprojekt_subhash("fe93bb3a7743c39e12c8d7c4a864dff1") == "8410a"
