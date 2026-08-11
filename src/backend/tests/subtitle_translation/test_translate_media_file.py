from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation import (
    translate_media_file as translate_media_file_module,
)
from legendarr_backend.subtitle_translation.translate_media_file import translate_media_file

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:01,000
hello

"""


class _UppercaseProvider:
    name = "uppercase"

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        return text.upper()


class _FailingProvider:
    name = "failing"

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        raise RuntimeError("boom")


def _movie(session, tmp_path: Path, **overrides) -> Movie:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name="radarr",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    data = {"arr_service_id": service.id, "arr_id": 1, "title": "Foo", "remote_path": "/remote/Foo"}
    data.update(overrides)
    movie = Movie(**data)
    session.add(movie)
    session.commit()
    return movie


def _media_file(session, movie: Movie) -> MediaFile:
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/Foo.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def _profile(session, **overrides) -> LanguageProfile:
    data = {
        "name": "default",
        "source_languages": "en",
        "target_languages": "pt-BR",
        "is_default": True,
    }
    data.update(overrides)
    profile = LanguageProfile(**data)
    session.add(profile)
    session.commit()
    return profile


def _write_video_and_source_subtitle(tmp_path: Path, session, media_file: MediaFile) -> Path:
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    (tmp_path / "Foo" / "Foo.en.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    scan_subtitles_for_media_file(session, media_file, video)
    session.commit()
    return video


def test_translate_media_file_skips_when_no_language_profile(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason == "no_language_profile"


def test_translate_media_file_skips_when_no_source_subtitle(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason == "no_source_subtitle"


def test_translate_media_file_skips_when_no_provider_configured(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason == "no_provider_configured"


def test_translate_media_file_writes_translated_srt_and_reconciles_subtitle_row(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == ["pt-BR"]
    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "HELLO" in output.read_text(encoding="utf-8")


def test_translate_media_file_falls_back_to_next_provider_on_failure(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_FailingProvider(), _UppercaseProvider()],
    )

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == ["pt-BR"]


def test_translate_media_file_skips_target_language_already_translated(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.pt-BR.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason is None


def test_translate_media_file_skips_target_language_already_covered_by_embedded_track(
    in_memory_session, tmp_path, monkeypatch
):
    """An extracted embedded track can't be picked as the *source* (see
    `_pick_source_subtitle` — no acquisition fallback yet), but it does satisfy a
    *target* language: retranslating from scratch would just duplicate what's already on
    disk. Matched region-blind (`language_codes.normalize_language_code`), since ffprobe
    can't tell e.g. Brazilian from European Portuguese — the profile's "pt-BR" target is
    satisfied by a "pt" embedded row."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="pt",
            origin=SubtitleOrigin.EMBEDDED,
            relative_path="Foo/Foo.embedded.3.por.srt",
            track_index=3,
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason is None
