import json
import subprocess
from pathlib import Path

import pytest
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import (
    EmbeddedSubtitleTrack,
    extract_embedded_subtitle_track,
    extract_pgs_subtitle_stream,
    probe_embedded_subtitle_tracks,
)

FFPROBE_STREAMS = {
    "streams": [
        {
            "index": 2,
            "codec_name": "subrip",
            "tags": {"language": "jpn"},
            "disposition": {"forced": 0, "hearing_impaired": 0},
        },
        {
            "index": 3,
            "codec_name": "ass",
            "tags": {"language": "eng"},
            "disposition": {"forced": 1, "hearing_impaired": 1},
        },
        {
            "index": 4,
            "codec_name": "hdmv_pgs_subtitle",
            "tags": {"language": "por"},
            "disposition": {"forced": 0, "hearing_impaired": 0},
        },
    ]
}


def _completed_process(stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


def test_probe_returns_text_and_image_based_tracks_with_language_and_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed_process(json.dumps(FFPROBE_STREAMS))
    )

    tracks = probe_embedded_subtitle_tracks(tmp_path / "movie.mkv", timeout_seconds=30.0)

    assert tracks == [
        EmbeddedSubtitleTrack(
            index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
        ),
        EmbeddedSubtitleTrack(
            index=3, codec_name="ass", language="eng", forced=True, hearing_impaired=True
        ),
        EmbeddedSubtitleTrack(
            index=4,
            codec_name="hdmv_pgs_subtitle",
            language="por",
            forced=False,
            hearing_impaired=False,
        ),
    ]


def test_probe_excludes_vobsub_and_dvb_codecs(monkeypatch, tmp_path):
    """VobSub (`dvd_subtitle`) and DVB (`dvb_subtitle`) stay out of scope — ROADMAP.md
    0.14.0 only wires up PGS OCR."""
    streams = {
        "streams": [
            {
                "index": 2,
                "codec_name": "dvd_subtitle",
                "tags": {"language": "eng"},
                "disposition": {},
            },
            {
                "index": 3,
                "codec_name": "dvb_subtitle",
                "tags": {"language": "eng"},
                "disposition": {},
            },
        ]
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed_process(json.dumps(streams)))

    tracks = probe_embedded_subtitle_tracks(tmp_path / "movie.mkv", timeout_seconds=30.0)

    assert tracks == []


def test_probe_defaults_language_to_und_when_no_tag(monkeypatch, tmp_path):
    streams = {"streams": [{"index": 2, "codec_name": "mov_text", "tags": {}, "disposition": {}}]}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed_process(json.dumps(streams)))

    tracks = probe_embedded_subtitle_tracks(tmp_path / "movie.mkv", timeout_seconds=30.0)

    assert tracks == [
        EmbeddedSubtitleTrack(
            index=2, codec_name="mov_text", language="und", forced=False, hearing_impaired=False
        )
    ]


def test_probe_returns_empty_list_when_ffprobe_binary_is_missing(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("ffprobe not found")

    monkeypatch.setattr(subprocess, "run", _raise)

    tracks = probe_embedded_subtitle_tracks(tmp_path / "movie.mkv", timeout_seconds=30.0)

    assert tracks == []


def test_probe_raises_on_nonzero_ffprobe_exit(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["ffprobe"])

    monkeypatch.setattr(subprocess, "run", _raise)

    with pytest.raises(subprocess.CalledProcessError):
        probe_embedded_subtitle_tracks(tmp_path / "movie.mkv", timeout_seconds=30.0)


def test_extract_invokes_ffmpeg_with_expected_map_and_codec(monkeypatch, tmp_path):
    captured = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        Path(cmd[-1]).touch()  # simulate ffmpeg writing its output
        return _completed_process("")

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.2.jpn.srt"
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )

    extract_embedded_subtitle_track(video_path, track, output_path, timeout_seconds=30.0)

    cmd = captured["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == str(video_path)
    assert "-map" in cmd and cmd[cmd.index("-map") + 1] == "0:2"
    assert "-c:s" in cmd and cmd[cmd.index("-c:s") + 1] == "srt"
    # The temp sibling's name ends in `.tmp`, not `.srt` — ffmpeg can't infer the muxer
    # from that extension, so `-f srt` has to say so explicitly (see the docstring).
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "srt"
    # ffmpeg is pointed at a temp sibling, not `output_path` itself — see below.
    assert cmd[-1] == str(output_path) + ".tmp"
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == 30.0


def test_extract_replaces_output_path_only_after_ffmpeg_succeeds(monkeypatch, tmp_path):
    def _run(cmd, **kwargs):
        Path(cmd[-1]).touch()
        return _completed_process("")

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.2.jpn.srt"
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )

    extract_embedded_subtitle_track(video_path, track, output_path, timeout_seconds=30.0)

    assert output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_extract_cleans_up_temp_file_and_reraises_on_ffmpeg_failure(monkeypatch, tmp_path):
    def _run(cmd, **kwargs):
        Path(cmd[-1]).touch()  # ffmpeg wrote a partial file before failing
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.2.jpn.srt"
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )

    with pytest.raises(subprocess.CalledProcessError):
        extract_embedded_subtitle_track(video_path, track, output_path, timeout_seconds=30.0)

    assert not output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_extract_skips_silently_when_ffmpeg_binary_is_missing(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(subprocess, "run", _raise)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.2.jpn.srt"
    track = EmbeddedSubtitleTrack(
        index=2, codec_name="subrip", language="jpn", forced=False, hearing_impaired=False
    )

    extract_embedded_subtitle_track(video_path, track, output_path, timeout_seconds=30.0)

    assert not output_path.exists()


def _pgs_track() -> EmbeddedSubtitleTrack:
    return EmbeddedSubtitleTrack(
        index=4,
        codec_name="hdmv_pgs_subtitle",
        language="por",
        forced=False,
        hearing_impaired=False,
    )


def test_extract_pgs_invokes_ffmpeg_with_expected_map_and_stream_copy(monkeypatch, tmp_path):
    captured = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        Path(cmd[-1]).touch()  # simulate ffmpeg writing its output
        return _completed_process("")

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.4.por.sup"

    extract_pgs_subtitle_stream(video_path, _pgs_track(), output_path, timeout_seconds=30.0)

    cmd = captured["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-i" in cmd and cmd[cmd.index("-i") + 1] == str(video_path)
    assert "-map" in cmd and cmd[cmd.index("-map") + 1] == "0:4"
    assert "-c:s" in cmd and cmd[cmd.index("-c:s") + 1] == "copy"
    assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "sup"
    assert cmd[-1] == str(output_path) + ".tmp"
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == 30.0


def test_extract_pgs_replaces_output_path_only_after_ffmpeg_succeeds(monkeypatch, tmp_path):
    def _run(cmd, **kwargs):
        Path(cmd[-1]).touch()
        return _completed_process("")

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.4.por.sup"

    extract_pgs_subtitle_stream(video_path, _pgs_track(), output_path, timeout_seconds=30.0)

    assert output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_extract_pgs_cleans_up_temp_file_and_reraises_on_ffmpeg_failure(monkeypatch, tmp_path):
    def _run(cmd, **kwargs):
        Path(cmd[-1]).touch()
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", _run)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.4.por.sup"

    with pytest.raises(subprocess.CalledProcessError):
        extract_pgs_subtitle_stream(video_path, _pgs_track(), output_path, timeout_seconds=30.0)

    assert not output_path.exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_extract_pgs_skips_silently_when_ffmpeg_binary_is_missing(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(subprocess, "run", _raise)

    video_path = tmp_path / "movie.mkv"
    output_path = tmp_path / "movie.embedded.4.por.sup"

    extract_pgs_subtitle_stream(video_path, _pgs_track(), output_path, timeout_seconds=30.0)

    assert not output_path.exists()
