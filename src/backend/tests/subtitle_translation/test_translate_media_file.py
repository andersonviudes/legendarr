from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import add_blacklist_entry
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_media_subtitles import scan_subtitles_for_media_file
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation import (
    translate_media_file as translate_media_file_module,
)
from legendarr_backend.subtitle_translation.translate_media_file import translate_media_file
from sqlmodel import select

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:01,000
hello

"""


class _UppercaseProvider:
    name = "uppercase"

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
        return [text.upper() for text in texts]


class _FailingProvider:
    name = "failing"

    def translate_batch(
        self, texts: list[str], source_language: str, target_language: str
    ) -> list[str]:
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


def test_translate_media_file_skips_when_source_subtitle_file_missing_on_disk(
    in_memory_session, tmp_path, monkeypatch
):
    """The source subtitle's DB row can outlive its file on disk (e.g. deleted externally
    between a scan and a translation run) — skip cleanly instead of raising
    `FileNotFoundError`."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.en.srt").unlink()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(in_memory_session, media_file, video)

    assert result.translated_languages == []
    assert result.skipped_reason == "source_subtitle_missing_on_disk"


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


def test_translate_media_file_uses_manually_picked_external_source(
    in_memory_session, tmp_path, monkeypatch
):
    """A manual `source_subtitle_id` overrides `_pick_source_subtitle` outright — here for
    a subtitle in a language ("fr") that isn't even in the profile's `source_languages`
    ("en"), which the automatic pick would never consider."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.fr.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nbonjour\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()
    fr_subtitle = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file.id,
            Subtitle.language == "fr",
        )
    ).one()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(
        in_memory_session, media_file, video, source_subtitle_id=fr_subtitle.id
    )

    assert result.translated_languages == ["pt-BR"]
    output = (tmp_path / "Foo" / "Foo.pt-br.srt").read_text(encoding="utf-8")
    assert "BONJOUR" in output
    assert "HELLO" not in output


def test_translate_media_file_uses_manually_picked_embedded_source(
    in_memory_session, tmp_path, monkeypatch
):
    """A manual pick can even override the automatic path's external-over-embedded
    preference: an external `en` subtitle exists (what `_pick_source_subtitle` would
    normally choose), but `source_subtitle_id` explicitly names the embedded track
    instead, and that's what gets used."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.embedded.3.deu.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nembedded\n\n", encoding="utf-8"
    )
    embedded_subtitle = Subtitle(
        media_file_id=media_file.id,
        language="de",
        origin=SubtitleOrigin.EMBEDDED,
        relative_path="Foo/Foo.embedded.3.deu.srt",
        track_index=3,
        content_hash="test-hash",
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(embedded_subtitle)
    in_memory_session.commit()
    in_memory_session.refresh(embedded_subtitle)
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(
        in_memory_session, media_file, video, source_subtitle_id=embedded_subtitle.id
    )

    assert result.translated_languages == ["pt-BR"]
    output = (tmp_path / "Foo" / "Foo.pt-br.srt").read_text(encoding="utf-8")
    assert "EMBEDDED" in output
    assert "HELLO" not in output


def test_translate_media_file_skips_when_source_subtitle_id_not_found(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)

    result = translate_media_file(in_memory_session, media_file, video, source_subtitle_id=999999)

    assert result.translated_languages == []
    assert result.skipped_reason == "source_subtitle_not_found"


def test_translate_media_file_skips_when_source_subtitle_id_belongs_to_another_media_file(
    in_memory_session, tmp_path
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)

    # A second file on the *same* movie — the point is only that its subtitle's
    # `media_file_id` differs from `media_file.id`.
    other_media_file = MediaFile(
        movie_id=movie.id,
        relative_path="Foo/Foo2.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(other_media_file)
    in_memory_session.commit()
    other_video = tmp_path / "Foo" / "Foo2.mkv"
    other_video.touch()
    (tmp_path / "Foo" / "Foo2.en.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    scan_subtitles_for_media_file(in_memory_session, other_media_file, other_video)
    in_memory_session.commit()
    other_source = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == other_media_file.id,
            Subtitle.language == "en",
        )
    ).one()

    result = translate_media_file(
        in_memory_session, media_file, video, source_subtitle_id=other_source.id
    )

    assert result.translated_languages == []
    assert result.skipped_reason == "source_subtitle_not_found"


def test_translate_media_file_manual_source_still_skips_already_translated_target(
    in_memory_session, tmp_path, monkeypatch
):
    """A manually-picked source doesn't bypass `_missing_targets`'s staleness check — a
    target already covered by a non-stale external subtitle is still left alone, same as
    the automatic path."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.pt-BR.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()
    source_subtitle = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file.id,
            Subtitle.language == "en",
        )
    ).one()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(
        in_memory_session, media_file, video, source_subtitle_id=source_subtitle.id
    )

    assert result.translated_languages == []
    assert result.skipped_reason is None


def test_translate_media_file_skips_retranslation_when_source_unchanged(
    in_memory_session, tmp_path, monkeypatch
):
    """The second run reuses the `content_hash` stamp from the first — no need to touch
    the provider chain again for an unchanged source."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )
    first = translate_media_file(in_memory_session, media_file, video)
    assert first.translated_languages == ["pt-BR"]

    second = translate_media_file(in_memory_session, media_file, video)

    assert second.translated_languages == []
    assert second.skipped_reason is None


def test_translate_media_file_retranslates_when_source_content_changes(
    in_memory_session, tmp_path, monkeypatch
):
    """A target subtitle stamped with a stale `translated_from_hash` (the source `.srt`
    was replaced/edited since) counts as missing again, unlike a target that was never
    produced by translation in the first place."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )
    first = translate_media_file(in_memory_session, media_file, video)
    assert first.translated_languages == ["pt-BR"]
    translated_row = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file.id,
            Subtitle.language == "pt-br",
        )
    ).one()
    source_row = in_memory_session.exec(
        select(Subtitle).where(
            Subtitle.media_file_id == media_file.id,
            Subtitle.language == "en",
        )
    ).one()
    assert translated_row.translated_from_hash == source_row.content_hash

    (tmp_path / "Foo" / "Foo.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\ngoodbye\n\n", encoding="utf-8"
    )
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()

    second = translate_media_file(in_memory_session, media_file, video)

    assert second.translated_languages == ["pt-BR"]
    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "GOODBYE" in output.read_text(encoding="utf-8")


def test_translate_media_file_falls_back_to_embedded_source_when_no_external_matches(
    in_memory_session, tmp_path, monkeypatch
):
    """No external `.en.srt` exists, but an already-extracted embedded track in the
    profile's source language does — `_pick_source_subtitle` falls back to it."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session)
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True)
    video.touch()
    (tmp_path / "Foo" / "Foo.embedded.3.eng.srt").write_text(SAMPLE_SRT, encoding="utf-8")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EMBEDDED,
            relative_path="Foo/Foo.embedded.3.eng.srt",
            track_index=3,
            content_hash="test-hash",
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

    assert result.translated_languages == ["pt-BR"]
    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "HELLO" in output.read_text(encoding="utf-8")


def test_translate_media_file_prefers_external_over_higher_priority_embedded_source(
    in_memory_session, tmp_path, monkeypatch
):
    """`ja` outranks `en` in the profile's source language list, and only an embedded `ja`
    track exists, but an external `en` subtitle also exists — external wins globally,
    it's never displaced by a higher-priority embedded language (see
    `_pick_source_subtitle`)."""
    embedded_srt = """1
00:00:00,000 --> 00:00:01,000
embedded

"""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session, source_languages="ja,en")
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    (tmp_path / "Foo" / "Foo.embedded.3.jpn.srt").write_text(embedded_srt, encoding="utf-8")
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="ja",
            origin=SubtitleOrigin.EMBEDDED,
            relative_path="Foo/Foo.embedded.3.jpn.srt",
            track_index=3,
            content_hash="test-hash",
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

    assert result.translated_languages == ["pt-BR"]
    output = tmp_path / "Foo" / "Foo.pt-br.srt"
    assert "HELLO" in output.read_text(encoding="utf-8")
    assert "EMBEDDED" not in output.read_text(encoding="utf-8")


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
            content_hash="test-hash",
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


def test_translate_media_file_skips_a_blacklisted_target_language_automatically(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="pt-BR", origin="translated"
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
    assert not (tmp_path / "Foo" / "Foo.pt-br.srt").exists()


def test_translate_media_file_manual_retry_clears_the_blacklist(
    in_memory_session, tmp_path, monkeypatch
):
    """An explicit manual "Translate from this" is exempt from the automatic block, and
    clears it for whichever target language it actually retranslates — so a later
    periodic run isn't blocked by a now-stale blacklist entry."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    assert media_file.id is not None
    _profile(in_memory_session)
    video = _write_video_and_source_subtitle(tmp_path, in_memory_session, media_file)
    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="pt-BR", origin="translated"
    )
    in_memory_session.commit()
    source = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id, Subtitle.language == "en")
    ).one()
    monkeypatch.setattr(
        translate_media_file_module,
        "resolve_provider_chain",
        lambda session, default_kind=None: [_UppercaseProvider()],
    )

    result = translate_media_file(
        in_memory_session, media_file, video, source_subtitle_id=source.id
    )
    assert result.translated_languages == ["pt-BR"]

    # The blacklist is now cleared — a later automatic run no longer skips it.
    (tmp_path / "Foo" / "Foo.pt-br.srt").unlink()
    scan_subtitles_for_media_file(in_memory_session, media_file, video)
    in_memory_session.commit()
    second_result = translate_media_file(in_memory_session, media_file, video)
    assert second_result.translated_languages == ["pt-BR"]
