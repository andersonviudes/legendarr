from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie, Series
from legendarr_backend.subtitle_acquisition import (
    acquire_media_file_subtitle as acquire_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition import search_context as search_context_module
from legendarr_backend.subtitle_acquisition.acquire_media_file_subtitle import (
    acquire_subtitle_for_media_file,
)
from legendarr_backend.subtitle_acquisition.models import AcquiredSubtitle, AcquisitionFailure
from legendarr_backend.subtitle_acquisition.probe_embedded_audio import EmbeddedAudioTrack
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from sqlmodel import select


class _FakeProvider:
    name = "fake"

    def __init__(self, results=None, text="1\n00:00:00,000 --> 00:00:15,000\nHi\n\n"):
        self.results = (
            results
            if results is not None
            else [SubtitleSearchResult(release_name="Foo", download_id="1", language="en")]
        )
        self.text = text
        self.search_calls = []

    def search(
        self,
        title,
        language,
        *,
        imdb_id=None,
        moviehash=None,
        season=None,
        episode=None,
        video_path=None,
        tvdb_id=None,
    ):
        self.search_calls.append(
            {
                "title": title,
                "language": language,
                "imdb_id": imdb_id,
                "moviehash": moviehash,
                "season": season,
                "episode": episode,
                "video_path": video_path,
                "tvdb_id": tvdb_id,
            }
        )
        return self.results

    def download(self, result):
        return self.text


class _FailingProvider:
    name = "failing"

    def search(
        self,
        title,
        language,
        *,
        imdb_id=None,
        moviehash=None,
        season=None,
        episode=None,
        video_path=None,
        tvdb_id=None,
    ):
        raise RuntimeError("boom")

    def download(self, result):
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
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo",
        "remote_path": "/remote/Foo",
        "imdb_id": "tt1234567",
    }
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


def _series(session, tmp_path: Path, **overrides) -> Series:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr",
            service_type="sonarr",
            host="sonarr",
            port=8989,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    data = {
        "arr_service_id": service.id,
        "arr_id": 1,
        "title": "Foo",
        "remote_path": "/remote/Foo",
    }
    data.update(overrides)
    series = Series(**data)
    session.add(series)
    session.commit()
    return series


def _series_media_file(session, series: Series) -> MediaFile:
    media_file = MediaFile(
        series_id=series.id,
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


def _write_video(tmp_path: Path) -> Path:
    video = tmp_path / "Foo" / "Foo.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    return video


def _use_chain(monkeypatch, *providers):
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: list(providers),
    )


def test_acquire_subtitle_skips_when_no_language_profile(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language is None
    assert result.skipped_reason == "no_language_profile"


def test_acquire_subtitle_is_a_noop_when_a_source_language_subtitle_already_exists(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    assert media_file.id is not None
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            content_hash="test-hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result == acquire_media_file_subtitle_module.AcquisitionResult()
    assert provider.search_calls == []


def test_acquire_subtitle_skips_when_no_provider_configured(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_provider_configured"


def test_acquire_subtitle_skips_when_nothing_clears_the_match_cutoff(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            )
        ]
    )
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language is None
    assert result.skipped_reason == "no_match_found"
    # No provider raised — a clean "nothing above the cutoff" pass isn't an error.
    assert list(in_memory_session.exec(select(AcquisitionFailure))) == []


def test_acquire_subtitle_records_a_failure_when_a_provider_raises_during_search(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FailingProvider())

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language is None
    assert result.skipped_reason == "no_match_found"
    failures = list(in_memory_session.exec(select(AcquisitionFailure)))
    assert len(failures) == 1
    assert failures[0].media_file_id == media_file.id
    assert failures[0].language == "en"
    assert "failing" in failures[0].error_message
    assert "boom" in failures[0].error_message


def test_acquire_subtitle_downloads_writes_and_rescans(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"
    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hi" in output.read_text(encoding="utf-8")
    rows = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert any(row.language == "en" and row.origin == SubtitleOrigin.EXTERNAL for row in rows)


def test_acquire_subtitle_passes_video_path_to_the_provider(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)

    acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert provider.search_calls[0]["video_path"] == video


def test_acquire_subtitle_passes_movie_imdb_id_to_the_provider(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path, imdb_id="tt7654321")
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)

    acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert provider.search_calls[0]["imdb_id"] == "tt7654321"
    assert provider.search_calls[0]["title"] == "Foo"


def test_acquire_subtitle_passes_series_season_episode_to_the_provider(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path, tvdb_id=389597)
    media_file = _series_media_file(in_memory_session, series)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)
    monkeypatch.setattr(
        search_context_module,
        "resolve_media_file_episode",
        lambda session, media_file: EpisodeItem(
            season_number=1, episode_number=2, title="Foo", relative_path="Foo/Foo.mkv"
        ),
    )

    acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert provider.search_calls[0]["season"] == 1
    assert provider.search_calls[0]["episode"] == 2
    assert provider.search_calls[0]["imdb_id"] is None
    assert provider.search_calls[0]["tvdb_id"] == 389597


def test_acquire_subtitle_passes_none_season_episode_when_resolution_fails(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path)
    media_file = _series_media_file(in_memory_session, series)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    provider = _FakeProvider()
    _use_chain(monkeypatch, provider)
    monkeypatch.setattr(
        search_context_module,
        "resolve_media_file_episode",
        lambda session, media_file: None,
    )

    acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert provider.search_calls[0]["season"] is None
    assert provider.search_calls[0]["episode"] is None


def test_acquire_subtitle_rejects_a_candidate_that_fails_must_not_contain(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, release_name_must_not_contain="CAM")
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        results=[SubtitleSearchResult(release_name="Foo.CAM", download_id="1", language="en")]
    )
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    # "Foo.CAM" would otherwise clear the match cutoff against "Foo" — must_not_contain
    # rejects it before scoring even runs.
    assert result.acquired_language is None
    assert result.skipped_reason == "no_match_found"


def test_acquire_subtitle_rejects_a_candidate_missing_every_must_contain_term(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, release_name_must_contain="PROPER,REPACK")
    video = _write_video(tmp_path)
    provider = _FakeProvider()  # release_name="Foo", no PROPER/REPACK
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language is None
    assert result.skipped_reason == "no_match_found"


def test_acquire_subtitle_downloads_a_candidate_that_satisfies_must_contain(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, release_name_must_contain="PROPER,REPACK")
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        results=[SubtitleSearchResult(release_name="Foo.PROPER", download_id="1", language="en")]
    )
    _use_chain(monkeypatch, provider)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"


def test_acquire_subtitle_falls_back_to_the_next_provider_on_failure(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    working = _FakeProvider()
    _use_chain(monkeypatch, _FailingProvider(), working)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"
    # A recovered fallback isn't a failure — nothing worth surfacing on the History view.
    assert list(in_memory_session.exec(select(AcquisitionFailure))) == []


def test_acquire_subtitle_falls_back_to_the_next_provider_on_quality_gate_failure(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    broken = _FakeProvider(text="too short to be a real subtitle")
    working = _FakeProvider()
    _use_chain(monkeypatch, broken, working)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"


def test_acquire_subtitle_tries_the_next_source_language_when_the_first_has_no_match(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, source_languages="en,ja")
    video = _write_video(tmp_path)

    class _LanguageAwareProvider:
        name = "language-aware"

        def search(
            self,
            title,
            language,
            *,
            imdb_id=None,
            moviehash=None,
            season=None,
            episode=None,
            video_path=None,
            tvdb_id=None,
        ):
            if language != "ja":
                return []
            return [SubtitleSearchResult(release_name="Foo", download_id="1", language="ja")]

        def download(self, result):
            return "1\n00:00:00,000 --> 00:00:15,000\nこんにちは\n\n"

    _use_chain(monkeypatch, _LanguageAwareProvider())

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "ja"
    output = tmp_path / "Foo" / "Foo.ja.srt"
    assert output.exists()


def test_acquire_subtitle_calls_on_progress_per_provider_attempt(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FailingProvider(), _FakeProvider())
    calls: list[tuple[int, int, str, str | None]] = []

    result = acquire_subtitle_for_media_file(
        in_memory_session, media_file, video, on_progress=lambda *args: calls.append(args)
    )

    assert result.acquired_language == "en"
    assert calls == [
        (1, 1, "en", None),
        (1, 1, "en", "failing"),
        (1, 1, "en", "fake"),
    ]


def test_acquire_subtitle_calls_on_progress_for_each_source_language_tried(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, source_languages="en,ja")
    video = _write_video(tmp_path)

    class _LanguageAwareProvider:
        name = "language-aware"

        def search(
            self,
            title,
            language,
            *,
            imdb_id=None,
            moviehash=None,
            season=None,
            episode=None,
            video_path=None,
            tvdb_id=None,
        ):
            if language != "ja":
                return []
            return [SubtitleSearchResult(release_name="Foo", download_id="1", language="ja")]

        def download(self, result):
            return "1\n00:00:00,000 --> 00:00:15,000\nこんにちは\n\n"

    _use_chain(monkeypatch, _LanguageAwareProvider())
    calls: list[tuple[int, int, str, str | None]] = []

    result = acquire_subtitle_for_media_file(
        in_memory_session, media_file, video, on_progress=lambda *args: calls.append(args)
    )

    assert result.acquired_language == "ja"
    assert calls == [
        (1, 2, "en", None),
        (1, 2, "en", "language-aware"),
        (2, 2, "ja", None),
        (2, 2, "ja", "language-aware"),
    ]


def _use_speech_to_text_fallback(monkeypatch, *, track_language="eng"):
    track = EmbeddedAudioTrack(index=1, codec_name="aac", language=track_language)
    monkeypatch.setattr(
        acquire_media_file_subtitle_module, "probe_embedded_audio_tracks", lambda *a, **k: [track]
    )

    def _fake_extract(video_path, track, output_path, *, timeout_seconds):
        output_path.write_bytes(b"fake-audio")

    monkeypatch.setattr(acquire_media_file_subtitle_module, "extract_audio_track", _fake_extract)

    def _fake_transcribe(
        audio_path, language, output_path, *, model_size, model_dir, timeout_seconds
    ):
        output_path.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n\n")

    monkeypatch.setattr(
        acquire_media_file_subtitle_module, "transcribe_audio_track", _fake_transcribe
    )
    return track


def test_acquire_subtitle_uses_speech_to_text_fallback_when_no_provider_configured(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, speech_to_text_fallback=True)
    video = _write_video(tmp_path)
    _use_speech_to_text_fallback(monkeypatch)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"
    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Hello" in output.read_text(encoding="utf-8")
    subtitle = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).first()
    assert subtitle is not None
    assert subtitle.origin == SubtitleOrigin.EXTERNAL
    assert subtitle.language == "en"
    # No AcquiredSubtitle row — that table is provider-download provenance only, and a
    # locally-generated transcript has no release/download id/score to record.
    assert in_memory_session.exec(select(AcquiredSubtitle)).first() is None


def test_acquire_subtitle_falls_back_to_speech_to_text_after_the_provider_chain_finds_nothing(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, speech_to_text_fallback=True)
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            )
        ]
    )
    _use_chain(monkeypatch, provider)
    _use_speech_to_text_fallback(monkeypatch)

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language == "en"


def test_acquire_subtitle_does_not_try_speech_to_text_when_toggle_is_off(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    probe_calls = []
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "probe_embedded_audio_tracks",
        lambda *a, **k: probe_calls.append(1) or [],
    )

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_provider_configured"
    assert probe_calls == []


def test_acquire_subtitle_reports_no_match_found_when_speech_to_text_also_fails(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, speech_to_text_fallback=True)
    video = _write_video(tmp_path)
    provider = _FakeProvider(
        results=[
            SubtitleSearchResult(
                release_name="Completely.Unrelated.Release", download_id="1", language="en"
            )
        ]
    )
    _use_chain(monkeypatch, provider)
    monkeypatch.setattr(
        acquire_media_file_subtitle_module, "probe_embedded_audio_tracks", lambda *a, **k: []
    )

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.acquired_language is None
    assert result.skipped_reason == "no_match_found"


def test_acquire_subtitle_speech_to_text_prefers_the_track_matching_source_language(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session, source_languages="ja,en", speech_to_text_fallback=True)
    video = _write_video(tmp_path)
    tracks = [
        EmbeddedAudioTrack(index=1, codec_name="aac", language="eng"),
        EmbeddedAudioTrack(index=2, codec_name="aac", language="jpn"),
    ]
    monkeypatch.setattr(
        acquire_media_file_subtitle_module, "probe_embedded_audio_tracks", lambda *a, **k: tracks
    )
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "extract_audio_track",
        lambda video_path, track, output_path, *, timeout_seconds: output_path.write_bytes(b"x"),
    )
    monkeypatch.setattr(
        acquire_media_file_subtitle_module,
        "transcribe_audio_track",
        lambda audio_path, language, output_path, *, model_size, model_dir, timeout_seconds: (
            output_path.write_text("1\n00:00:00,000 --> 00:00:02,000\nこんにちは\n\n")
        ),
    )

    result = acquire_subtitle_for_media_file(in_memory_session, media_file, video)

    # "ja" is first in the profile's priority order, and the second track is tagged
    # "jpn" — picked over the first (English) track despite index order.
    assert result.acquired_language == "ja"
