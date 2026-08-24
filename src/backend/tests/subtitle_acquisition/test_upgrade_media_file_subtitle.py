from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition import (
    upgrade_media_file_subtitle as upgrade_media_file_subtitle_module,
)
from legendarr_backend.subtitle_acquisition.manage_acquired_subtitle import (
    get_acquired_subtitle,
    record_acquired_subtitle,
)
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import add_blacklist_entry
from legendarr_backend.subtitle_acquisition.match_score import CandidateEvaluation
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleSearchResult
from legendarr_backend.subtitle_acquisition.upgrade_media_file_subtitle import (
    upgrade_subtitle_for_media_file,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin


class _FakeProvider:
    name = "fake"

    def __init__(self, results=None, text="1\n00:00:00,000 --> 00:00:01,000\nBetter\n\n"):
        self.results = results if results is not None else []
        self.text = text
        self.download_calls = []

    def search(self, title, language, **kwargs):
        return self.results

    def download(self, result):
        self.download_calls.append(result)
        return self.text


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
        upgrade_media_file_subtitle_module,
        "resolve_subtitle_provider_chain",
        lambda session: list(providers),
    )


def _acquired_subtitle(session, media_file: MediaFile, *, language="en", score: float) -> Subtitle:
    """An external `Subtitle` the system acquired itself, at `score` — same shape
    `acquire_subtitle_for_media_file` leaves behind, built directly so a test can pick
    the exact baseline score an upgrade candidate needs to beat."""
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language=language,
        origin=SubtitleOrigin.EXTERNAL,
        relative_path=f"Foo/Foo.{language}.srt",
        content_hash="old-hash",
        scanned_at=datetime.now(UTC),
    )
    session.add(subtitle)
    session.commit()
    record_acquired_subtitle(
        session,
        media_file.id,
        language,
        provider="old-provider",
        release_name="Foo.OLD",
        download_id="old-1",
        evaluation=CandidateEvaluation(score=score, title_similarity=score, attribute_matches={}),
    )
    session.commit()
    return subtitle


def test_upgrade_skips_when_no_language_profile(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    video = _write_video(tmp_path)

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_language_profile"


def test_upgrade_skips_when_there_is_no_acquired_source_subtitle(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _use_chain(monkeypatch, _FakeProvider())

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_upgradeable_subtitle"


def test_upgrade_skips_a_manually_uploaded_subtitle(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    assert media_file.id is not None
    # No `AcquiredSubtitle` row — same as a manually uploaded external subtitle.
    in_memory_session.add(
        Subtitle(
            media_file_id=media_file.id,
            language="en",
            origin=SubtitleOrigin.EXTERNAL,
            relative_path="Foo/Foo.en.srt",
            content_hash="hash",
            scanned_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()
    _use_chain(monkeypatch, _FakeProvider())

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_upgradeable_subtitle"


def test_upgrade_skips_when_no_provider_configured(in_memory_session, tmp_path):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _acquired_subtitle(in_memory_session, media_file, score=0.5)

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_provider_configured"


def test_upgrade_skips_when_nothing_scores_higher(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _acquired_subtitle(in_memory_session, media_file, score=1.0)
    provider = _FakeProvider(
        results=[SubtitleSearchResult(release_name="Foo", download_id="new-1", language="en")]
    )
    _use_chain(monkeypatch, provider)

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_upgrade_found"
    assert provider.download_calls == []


def test_upgrade_replaces_when_a_better_candidate_is_found(
    in_memory_session, tmp_path, monkeypatch
):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    subtitle = _acquired_subtitle(in_memory_session, media_file, score=0.1)
    provider = _FakeProvider(
        results=[SubtitleSearchResult(release_name="Foo", download_id="new-1", language="en")]
    )
    _use_chain(monkeypatch, provider)

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.upgraded_language == "en"
    output = tmp_path / "Foo" / "Foo.en.srt"
    assert "Better" in output.read_text(encoding="utf-8")
    assert subtitle.id is not None
    metadata = get_acquired_subtitle(in_memory_session, subtitle.id)
    assert metadata is not None
    assert metadata.provider == "fake"
    assert metadata.download_id == "new-1"
    assert metadata.score > 0.1


def test_upgrade_excludes_a_blacklisted_candidate(in_memory_session, tmp_path, monkeypatch):
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    _profile(in_memory_session)
    video = _write_video(tmp_path)
    _acquired_subtitle(in_memory_session, media_file, score=0.1)
    assert media_file.id is not None
    add_blacklist_entry(
        in_memory_session,
        media_file_id=media_file.id,
        language="en",
        origin="acquired",
        provider="fake",
        release_name="Foo",
        download_id="new-1",
    )
    in_memory_session.commit()
    provider = _FakeProvider(
        results=[SubtitleSearchResult(release_name="Foo", download_id="new-1", language="en")]
    )
    _use_chain(monkeypatch, provider)

    result = upgrade_subtitle_for_media_file(in_memory_session, media_file, video)

    assert result.skipped_reason == "no_upgrade_found"
    assert provider.download_calls == []
