from pathlib import Path

import pytest
from legendarr_backend.subtitle_discovery import ocr_embedded_subtitles as ocr_module
from legendarr_backend.subtitle_discovery.ocr_embedded_subtitles import ocr_pgs_track
from legendarr_backend.subtitle_discovery.pgs_format import PgsSubtitleCue
from legendarr_backend.subtitle_discovery.probe_embedded_subtitles import EmbeddedSubtitleTrack
from PIL import Image


def _track(language: str = "eng") -> EmbeddedSubtitleTrack:
    return EmbeddedSubtitleTrack(
        index=4,
        codec_name="hdmv_pgs_subtitle",
        language=language,
        forced=False,
        hearing_impaired=False,
    )


def _cue(start_ms: int, end_ms: int) -> PgsSubtitleCue:
    return PgsSubtitleCue(
        start_ms=start_ms, end_ms=end_ms, image=Image.new("RGBA", (2, 2), (0, 0, 0, 255))
    )


def _fake_extract_writes_sup(
    video_path: Path, track, output_path: Path, *, timeout_seconds: float
) -> None:
    output_path.write_bytes(b"fake sup bytes")


def _fake_extract_skips(
    video_path: Path, track, output_path: Path, *, timeout_seconds: float
) -> None:
    pass  # mirrors a missing ffmpeg binary: no file written


def test_ocr_pgs_track_writes_composed_srt_from_ocrd_cues(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: [_cue(0, 1000), _cue(1000, 2000)])
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["eng"])
    texts = iter(["Hello", "World"])
    monkeypatch.setattr(
        ocr_module.pytesseract, "image_to_string", lambda image, lang, timeout: next(texts)
    )

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    content = output_path.read_text()
    assert "Hello" in content
    assert "World" in content
    assert not output_path.with_name(output_path.name + ".sup.tmp").exists()
    assert not output_path.with_name(output_path.name + ".tmp").exists()


def test_ocr_pgs_track_drops_cues_that_ocr_to_empty_text(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: [_cue(0, 1000), _cue(1000, 2000)])
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["eng"])
    texts = iter(["", "  \n  "])  # both blank after strip()
    monkeypatch.setattr(
        ocr_module.pytesseract, "image_to_string", lambda image, lang, timeout: next(texts)
    )

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    # Nothing survived OCR — no `.srt` is written, same posture as a missing ffmpeg binary.
    assert not output_path.exists()


def test_ocr_pgs_track_skips_when_ffmpeg_binary_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_skips)
    called = []
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: called.append(data) or [])

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    assert not output_path.exists()
    assert called == []  # never got as far as parsing — there was nothing to parse


def test_ocr_pgs_track_cleans_up_sup_temp_file_even_when_parsing_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)

    def _raise(data):
        raise ValueError("bad sup data")

    monkeypatch.setattr(ocr_module, "parse_pgs", _raise)

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    with pytest.raises(ValueError):
        ocr_pgs_track(
            tmp_path / "movie.mkv",
            _track(),
            output_path,
            timeout_seconds=30.0,
            ocr_cue_timeout_seconds=10.0,
        )

    assert not output_path.with_name(output_path.name + ".sup.tmp").exists()
    assert not output_path.exists()


def test_ocr_pgs_track_uses_language_override_for_tesseract(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: [_cue(0, 1000)])
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["chi_sim"])
    captured_lang = {}

    def _image_to_string(image, lang, timeout):
        captured_lang["lang"] = lang
        return "你好"

    monkeypatch.setattr(ocr_module.pytesseract, "image_to_string", _image_to_string)

    output_path = tmp_path / "movie.embedded.4.chi.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(language="chi"),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    assert captured_lang["lang"] == "chi_sim"


def test_ocr_pgs_track_falls_back_to_english_when_language_pack_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: [_cue(0, 1000)])
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["eng"])
    captured_lang = {}

    def _image_to_string(image, lang, timeout):
        captured_lang["lang"] = lang
        return "hi"

    monkeypatch.setattr(ocr_module.pytesseract, "image_to_string", _image_to_string)

    output_path = tmp_path / "movie.embedded.4.kor.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(language="kor"),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    assert captured_lang["lang"] == "eng"


def test_ocr_pgs_track_stops_once_the_whole_track_budget_is_exhausted(monkeypatch, tmp_path):
    """`ocr_cue_timeout_seconds` only bounds a single cue — this is the aggregate cap over
    the whole track, so a track with many cues can't monopolize `scan_bulk`'s single
    worker forever (`scheduling/queues.py`).
    """
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(
        ocr_module, "parse_pgs", lambda data: [_cue(0, 1000), _cue(1000, 2000), _cue(2000, 3000)]
    )
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["eng"])
    monkeypatch.setattr(ocr_module, "MAX_OCR_TRACK_SECONDS", 10.0)
    # 1st call sets the deadline (now + 10). 2nd call (before cue 1) is still within
    # budget. 3rd call (before cue 2) is past it, so cue 2 and the untouched cue 3 are
    # both skipped.
    clock = iter([0.0, 0.0, 20.0])
    monkeypatch.setattr(ocr_module.time, "monotonic", lambda: next(clock))
    calls = []

    def _image_to_string(image, lang, timeout):
        calls.append(image)
        return "cue text"

    monkeypatch.setattr(ocr_module.pytesseract, "image_to_string", _image_to_string)

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    assert len(calls) == 1
    assert output_path.read_text().count("cue text") == 1


def test_ocr_pgs_track_skips_a_cue_whose_ocr_call_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr_module, "extract_pgs_subtitle_stream", _fake_extract_writes_sup)
    monkeypatch.setattr(ocr_module, "parse_pgs", lambda data: [_cue(0, 1000), _cue(1000, 2000)])
    monkeypatch.setattr(ocr_module.pytesseract, "get_languages", lambda config="": ["eng"])
    calls = iter([RuntimeError("tesseract timed out"), "Second cue text"])

    def _image_to_string(image, lang, timeout):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(ocr_module.pytesseract, "image_to_string", _image_to_string)

    output_path = tmp_path / "movie.embedded.4.eng.srt"
    ocr_pgs_track(
        tmp_path / "movie.mkv",
        _track(),
        output_path,
        timeout_seconds=30.0,
        ocr_cue_timeout_seconds=10.0,
    )

    content = output_path.read_text()
    assert "Second cue text" in content
