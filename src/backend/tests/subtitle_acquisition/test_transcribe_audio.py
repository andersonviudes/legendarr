import time
from dataclasses import dataclass

from legendarr_backend.subtitle_acquisition.audio_transcription import transcribe_audio
from legendarr_backend.subtitle_acquisition.audio_transcription.transcribe_audio import (
    _get_model,
    transcribe_audio_track,
)
from legendarr_backend.subtitle_discovery.subtitle_format import parse_srt


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str


class _FakeModel:
    def __init__(self, segments):
        self._segments = segments

    def transcribe(self, audio_path, language=None):
        return iter(self._segments), None


def _install_fake_model(monkeypatch, segments):
    monkeypatch.setattr(transcribe_audio, "_models", {})
    monkeypatch.setattr(
        transcribe_audio, "_get_model", lambda model_size, model_dir: _FakeModel(segments)
    )


def test_transcribe_writes_composed_srt_from_segments(monkeypatch, tmp_path):
    _install_fake_model(
        monkeypatch,
        [
            _FakeSegment(start=0.0, end=1.5, text=" Hello there "),
            _FakeSegment(start=1.5, end=3.0, text="General Kenobi"),
        ],
    )
    output_path = tmp_path / "movie.en.srt"

    transcribe_audio_track(
        tmp_path / "movie.audio.wav",
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=5.0,
    )

    lines = parse_srt(output_path.read_text())
    assert [line.text for line in lines] == ["Hello there", "General Kenobi"]
    assert lines[0].start_ms == 0
    assert lines[0].end_ms == 1500


def test_transcribe_drops_segments_that_are_empty_after_strip(monkeypatch, tmp_path):
    _install_fake_model(
        monkeypatch,
        [_FakeSegment(start=0.0, end=1.0, text="   "), _FakeSegment(start=1.0, end=2.0, text="ok")],
    )
    output_path = tmp_path / "movie.en.srt"

    transcribe_audio_track(
        tmp_path / "movie.audio.wav",
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=5.0,
    )

    lines = parse_srt(output_path.read_text())
    assert [line.text for line in lines] == ["ok"]


def test_transcribe_leaves_output_unwritten_when_nothing_survives(monkeypatch, tmp_path):
    _install_fake_model(monkeypatch, [_FakeSegment(start=0.0, end=1.0, text="   ")])
    output_path = tmp_path / "movie.en.srt"

    transcribe_audio_track(
        tmp_path / "movie.audio.wav",
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=5.0,
    )

    assert not output_path.exists()


def test_transcribe_gives_up_and_leaves_output_unwritten_on_timeout(monkeypatch, tmp_path):
    class _SlowModel:
        def transcribe(self, audio_path, language=None):
            time.sleep(1)
            return iter([]), None

    monkeypatch.setattr(transcribe_audio, "_models", {})
    monkeypatch.setattr(transcribe_audio, "_get_model", lambda model_size, model_dir: _SlowModel())
    output_path = tmp_path / "movie.en.srt"

    transcribe_audio_track(
        tmp_path / "movie.audio.wav",
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=0.05,
    )

    assert not output_path.exists()


def test_transcribe_swallows_exception_from_model_and_leaves_output_unwritten(
    monkeypatch, tmp_path
):
    class _BrokenModel:
        def transcribe(self, audio_path, language=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(transcribe_audio, "_models", {})
    monkeypatch.setattr(
        transcribe_audio, "_get_model", lambda model_size, model_dir: _BrokenModel()
    )
    output_path = tmp_path / "movie.en.srt"

    transcribe_audio_track(
        tmp_path / "movie.audio.wav",
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=5.0,
    )

    assert not output_path.exists()


def test_get_model_caches_instance_per_model_size_and_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(transcribe_audio, "_models", {})
    created = []

    class _FakeWhisperModel:
        def __init__(self, model_size, device, download_root):
            created.append((model_size, device, download_root))

    monkeypatch.setattr(transcribe_audio, "WhisperModel", _FakeWhisperModel)

    first = _get_model("base", tmp_path / "models")
    second = _get_model("base", tmp_path / "models")
    third = _get_model("small", tmp_path / "models")

    assert first is second
    assert first is not third
    assert len(created) == 2
