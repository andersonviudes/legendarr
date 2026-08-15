import subprocess
from pathlib import Path

from legendarr_backend.subtitle_timing_sync.sync_subtitle_timing import sync_subtitle_timing


def _completed_process() -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_sync_writes_temp_file_and_replaces_target_on_success(monkeypatch, tmp_path):
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text("original", encoding="utf-8")

    def fake_run(args, **kwargs):
        output_path = Path(args[args.index("-o") + 1])
        output_path.write_text("synced", encoding="utf-8")
        return _completed_process()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = sync_subtitle_timing(tmp_path / "movie.mkv", subtitle_path, timeout_seconds=30.0)

    assert result is True
    assert subtitle_path.read_text(encoding="utf-8") == "synced"
    assert not subtitle_path.with_name(f"{subtitle_path.stem}.tmp.srt").exists()


def test_sync_returns_false_when_ffsubsync_exits_zero_without_writing_output(monkeypatch, tmp_path):
    """`ffsubsync` can log an internal failure (e.g. an unrecognized output format) and
    still exit `0` — a zero return code alone isn't enough to call it a success."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed_process())
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text("original", encoding="utf-8")

    result = sync_subtitle_timing(tmp_path / "movie.mkv", subtitle_path, timeout_seconds=30.0)

    assert result is False
    assert subtitle_path.read_text(encoding="utf-8") == "original"


def test_sync_returns_false_when_ffsubsync_binary_is_missing(monkeypatch, tmp_path):
    def _raise(*args, **kwargs):
        raise FileNotFoundError("ffsubsync not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text("original", encoding="utf-8")

    result = sync_subtitle_timing(tmp_path / "movie.mkv", subtitle_path, timeout_seconds=30.0)

    assert result is False
    assert subtitle_path.read_text(encoding="utf-8") == "original"


def test_sync_returns_false_and_cleans_up_temp_file_on_non_zero_exit(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        output_path = Path(args[args.index("-o") + 1])
        output_path.write_text("partial", encoding="utf-8")
        raise subprocess.CalledProcessError(returncode=1, cmd=args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text("original", encoding="utf-8")

    result = sync_subtitle_timing(tmp_path / "movie.mkv", subtitle_path, timeout_seconds=30.0)

    assert result is False
    assert subtitle_path.read_text(encoding="utf-8") == "original"
    assert not subtitle_path.with_name(f"{subtitle_path.stem}.tmp.srt").exists()


def test_sync_returns_false_on_timeout(monkeypatch, tmp_path):
    def fake_run(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=30.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    subtitle_path = tmp_path / "movie.srt"
    subtitle_path.write_text("original", encoding="utf-8")

    result = sync_subtitle_timing(tmp_path / "movie.mkv", subtitle_path, timeout_seconds=30.0)

    assert result is False
