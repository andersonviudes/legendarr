import threading
import time
import wave
from dataclasses import dataclass

import pytest
from legendarr_backend.subtitle_acquisition.audio_transcription import transcribe_audio
from legendarr_backend.subtitle_acquisition.audio_transcription.transcribe_audio import (
    _get_model,
    transcribe_audio_track,
)
from legendarr_backend.subtitle_discovery.subtitle_format import parse_srt

_SAMPLE_RATE = 16_000


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str


class _FakeModel:
    def __init__(self, segments):
        self._segments = segments

    def transcribe(self, audio, language=None):
        return iter(self._segments), None


@pytest.fixture(autouse=True)
def _fresh_transcription_slot(monkeypatch):
    # A timed-out test leaves its abandoned thread holding the real slot for a moment —
    # give every test its own so none of them waits on (or releases) another's.
    monkeypatch.setattr(transcribe_audio, "_transcription_slot", threading.BoundedSemaphore(1))


def _write_wav(path, seconds: float) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        wav.writeframes(b"\x00\x00" * int(_SAMPLE_RATE * seconds))


def _install_fake_model(monkeypatch, model):
    monkeypatch.setattr(transcribe_audio, "_models", {})
    monkeypatch.setattr(transcribe_audio, "_get_model", lambda model_size, model_dir: model)


def _transcribe(tmp_path, *, timeout_seconds: float = 5.0, seconds: float = 1.0):
    audio_path = tmp_path / "movie.audio.wav"
    _write_wav(audio_path, seconds)
    output_path = tmp_path / "movie.en.srt"
    transcribe_audio_track(
        audio_path,
        "en",
        output_path,
        model_size="base",
        model_dir=tmp_path / "models",
        timeout_seconds=timeout_seconds,
    )
    return output_path


def test_transcribe_writes_composed_srt_from_segments(monkeypatch, tmp_path):
    _install_fake_model(
        monkeypatch,
        _FakeModel(
            [
                _FakeSegment(start=0.0, end=1.5, text=" Hello there "),
                _FakeSegment(start=1.5, end=3.0, text="General Kenobi"),
            ]
        ),
    )

    output_path = _transcribe(tmp_path)

    lines = parse_srt(output_path.read_text())
    assert [line.text for line in lines] == ["Hello there", "General Kenobi"]
    assert lines[0].start_ms == 0
    assert lines[0].end_ms == 1500


def test_transcribe_drops_segments_that_are_empty_after_strip(monkeypatch, tmp_path):
    _install_fake_model(
        monkeypatch,
        _FakeModel(
            [
                _FakeSegment(start=0.0, end=1.0, text="   "),
                _FakeSegment(start=1.0, end=2.0, text="ok"),
            ]
        ),
    )

    output_path = _transcribe(tmp_path)

    lines = parse_srt(output_path.read_text())
    assert [line.text for line in lines] == ["ok"]


def test_transcribe_leaves_output_unwritten_when_nothing_survives(monkeypatch, tmp_path):
    _install_fake_model(monkeypatch, _FakeModel([_FakeSegment(start=0.0, end=1.0, text="   ")]))

    output_path = _transcribe(tmp_path)

    assert not output_path.exists()


def test_transcribe_feeds_the_model_fixed_size_slices_and_offsets_their_timestamps(
    monkeypatch, tmp_path
):
    """Regression: handing `faster_whisper` the whole film at once made its decode + STFT peak
    at gigabytes for a long one. Each slice is transcribed on its own and shifted back."""
    monkeypatch.setattr(transcribe_audio, "_CHUNK_SECONDS", 2)
    slice_durations = []

    class _PerSliceModel:
        def transcribe(self, audio, language=None):
            with wave.open(audio, "rb") as wav:
                slice_durations.append(wav.getnframes() / wav.getframerate())
            return iter(
                [_FakeSegment(start=0.5, end=1.0, text=f"slice {len(slice_durations)}")]
            ), None

    _install_fake_model(monkeypatch, _PerSliceModel())

    output_path = _transcribe(tmp_path, seconds=5.0)

    assert slice_durations == [2.0, 2.0, 1.0]
    lines = parse_srt(output_path.read_text())
    assert [(line.index, line.start_ms, line.end_ms, line.text) for line in lines] == [
        (1, 500, 1000, "slice 1"),
        (2, 2500, 3000, "slice 2"),
        (3, 4500, 5000, "slice 3"),
    ]


def test_transcribe_gives_up_and_leaves_output_unwritten_on_timeout(monkeypatch, tmp_path):
    class _SlowModel:
        def transcribe(self, audio, language=None):
            time.sleep(2)
            return iter([]), None

    _install_fake_model(monkeypatch, _SlowModel())

    started = time.monotonic()
    output_path = _transcribe(tmp_path, timeout_seconds=0.05)
    elapsed = time.monotonic() - started

    # Regression check for the bug this test is named after: the call must give up and
    # return right after `timeout_seconds`, not block for the full duration of the
    # abandoned model call it can't cancel (a `ThreadPoolExecutor`'s `__exit__` used to
    # do exactly that via `shutdown(wait=True)`).
    assert elapsed < 1.0
    assert not output_path.exists()


def test_transcribe_stops_an_abandoned_run_at_the_next_segment(monkeypatch, tmp_path):
    consumed = []
    proceed = threading.Event()

    def _segments():
        for number in range(1, 6):
            consumed.append(number)
            if number == 1:
                proceed.wait(timeout=5)  # parked here until the caller has given up
            yield _FakeSegment(start=number, end=number + 1, text=f"segment {number}")

    class _Model:
        def transcribe(self, audio, language=None):
            return _segments(), None

    _install_fake_model(monkeypatch, _Model())

    output_path = _transcribe(tmp_path, timeout_seconds=0.05)
    proceed.set()
    deadline = time.monotonic() + 2
    while transcribe_audio._transcription_slot._value == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    assert not output_path.exists()
    # Without the cancel flag the abandoned thread would grind through all five segments.
    assert consumed == [1]


def test_transcribe_swallows_exception_from_model_and_leaves_output_unwritten(
    monkeypatch, tmp_path
):
    class _BrokenModel:
        def transcribe(self, audio, language=None):
            raise RuntimeError("boom")

    _install_fake_model(monkeypatch, _BrokenModel())

    output_path = _transcribe(tmp_path)

    assert not output_path.exists()


def test_transcribe_releases_the_slot_after_a_run_so_the_next_one_can_start(monkeypatch, tmp_path):
    _install_fake_model(monkeypatch, _FakeModel([_FakeSegment(start=0.0, end=1.0, text="ok")]))

    first = _transcribe(tmp_path)
    first.unlink()
    second = _transcribe(tmp_path)

    assert second.exists()


def test_transcribe_skips_when_another_transcription_never_frees_the_slot(monkeypatch, tmp_path):
    """Only one transcription runs at a time (CTranslate2 already uses every core, so a
    second only doubles the memory) — but a wedged one must not block the rest forever."""
    _install_fake_model(monkeypatch, _FakeModel([_FakeSegment(start=0.0, end=1.0, text="ok")]))
    transcribe_audio._transcription_slot.acquire()

    started = time.monotonic()
    output_path = _transcribe(tmp_path, timeout_seconds=0.05)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert not output_path.exists()


def test_get_model_caches_instance_per_model_size_and_dir_and_runs_int8(monkeypatch, tmp_path):
    monkeypatch.setattr(transcribe_audio, "_models", {})
    created = []

    class _FakeWhisperModel:
        def __init__(self, model_size, device, compute_type, download_root):
            created.append((model_size, device, compute_type, download_root))

    monkeypatch.setattr(transcribe_audio, "WhisperModel", _FakeWhisperModel)

    first = _get_model("base", tmp_path / "models")
    second = _get_model("base", tmp_path / "models")
    third = _get_model("small", tmp_path / "models")

    assert first is second
    assert first is not third
    assert len(created) == 2
    # float16 checkpoints would be upcast to float32 on a CPU under "default".
    assert {compute_type for _size, _device, compute_type, _root in created} == {"int8"}
