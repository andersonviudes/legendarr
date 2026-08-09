from pathlib import Path

from legendarr_backend.subtitle_discovery.scan_video_subtitles import (
    SubtitleOrigin,
    scan_video_subtitles,
)


def test_scan_video_subtitles_finds_external_srt_sibling(tmp_path: Path):
    video = tmp_path / "movie.mkv"
    video.touch()
    (tmp_path / "movie.pt-BR.srt").touch()

    subtitles = scan_video_subtitles(video)

    assert len(subtitles) == 1
    assert subtitles[0].origin == SubtitleOrigin.EXTERNAL
    assert subtitles[0].language == "pt-br"
