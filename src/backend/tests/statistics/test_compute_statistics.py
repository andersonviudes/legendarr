from datetime import UTC, datetime, timedelta

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.language_profiles.models import LanguageProfile
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.statistics.compute_statistics import DAILY_WINDOW_DAYS, compute_statistics
from legendarr_backend.statistics.schemas import BreakdownEntry
from legendarr_backend.subtitle_acquisition.models import AcquisitionAttempt
from legendarr_backend.subtitle_discovery.models import Subtitle
from legendarr_backend.subtitle_discovery.scan_video_subtitles import SubtitleOrigin
from legendarr_backend.subtitle_translation.models import TranslationAttempt


def _movie(session, tmp_path, **overrides) -> Movie:
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
        movie_id=movie.id, relative_path="Foo/Foo.mkv", size_bytes=1, scanned_at=datetime.now(UTC)
    )
    session.add(media_file)
    session.commit()
    return media_file


def _subtitle(session, media_file: MediaFile, language: str) -> Subtitle:
    assert media_file.id is not None
    subtitle = Subtitle(
        media_file_id=media_file.id,
        language=language,
        origin=SubtitleOrigin.EXTERNAL,
        relative_path=f"Foo/Foo.{language}.srt",
        content_hash="hash",
        scanned_at=datetime.now(UTC),
    )
    session.add(subtitle)
    session.commit()
    return subtitle


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


def test_compute_statistics_empty_state(in_memory_session):
    result = compute_statistics(in_memory_session)

    assert result.translated.total == 0
    assert result.acquired.total == 0
    assert len(result.translated.daily) == DAILY_WINDOW_DAYS
    assert len(result.acquired.daily) == DAILY_WINDOW_DAYS
    assert all(day.count == 0 for day in result.translated.daily)
    assert result.translated.by_profile == []
    assert result.translated.by_provider == []
    assert result.acquired.by_profile == []
    assert result.acquired.by_provider == []


def test_compute_statistics_counts_translation_and_acquisition_attempts(
    in_memory_session, tmp_path
):
    _profile(in_memory_session)
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    translated_subtitle = _subtitle(in_memory_session, media_file, "pt-br")
    acquired_subtitle = _subtitle(in_memory_session, media_file, "en")

    now = datetime.now(UTC)
    assert translated_subtitle.id is not None
    assert acquired_subtitle.id is not None
    in_memory_session.add(
        TranslationAttempt(
            subtitle_id=translated_subtitle.id,
            provider="deepl",
            source_language="en",
            target_language="pt-BR",
            translated_at=now,
        )
    )
    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=acquired_subtitle.id,
            provider="opensubtitles",
            release_name="Foo.WEB-DL",
            download_id="1",
            score=0.9,
            title_similarity=0.9,
            attempted_at=now,
        )
    )
    in_memory_session.commit()

    result = compute_statistics(in_memory_session)

    assert result.translated.total == 1
    assert result.translated.by_provider == [BreakdownEntry(label="deepl", count=1)]
    assert result.translated.by_profile == [BreakdownEntry(label="default", count=1)]
    today = now.date()
    assert next(day.count for day in result.translated.daily if day.date == today) == 1

    assert result.acquired.total == 1
    assert result.acquired.by_provider == [BreakdownEntry(label="opensubtitles", count=1)]
    assert result.acquired.by_profile == [BreakdownEntry(label="default", count=1)]


def test_compute_statistics_groups_by_provider_highest_count_first(in_memory_session, tmp_path):
    _profile(in_memory_session)
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    subtitle = _subtitle(in_memory_session, media_file, "pt-br")
    assert subtitle.id is not None

    now = datetime.now(UTC)
    for provider in ["deepl", "deepl", "google"]:
        in_memory_session.add(
            TranslationAttempt(
                subtitle_id=subtitle.id,
                provider=provider,
                source_language="en",
                target_language="pt-BR",
                translated_at=now,
            )
        )
    in_memory_session.commit()

    result = compute_statistics(in_memory_session)

    assert result.translated.total == 3
    assert result.translated.by_provider == [
        BreakdownEntry(label="deepl", count=2),
        BreakdownEntry(label="google", count=1),
    ]


def test_compute_statistics_daily_window_excludes_old_attempts_from_trend_but_not_totals(
    in_memory_session, tmp_path
):
    _profile(in_memory_session)
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    subtitle = _subtitle(in_memory_session, media_file, "pt-br")
    assert subtitle.id is not None

    old_at = datetime.now(UTC) - timedelta(days=DAILY_WINDOW_DAYS + 5)
    in_memory_session.add(
        TranslationAttempt(
            subtitle_id=subtitle.id,
            provider="deepl",
            source_language="en",
            target_language="pt-BR",
            translated_at=old_at,
        )
    )
    in_memory_session.commit()

    result = compute_statistics(in_memory_session)

    assert result.translated.total == 1
    assert all(day.count == 0 for day in result.translated.daily)
    assert result.translated.by_provider == [BreakdownEntry(label="deepl", count=1)]


def test_compute_statistics_falls_back_to_no_profile_label_when_none_resolves(
    in_memory_session, tmp_path
):
    """No `LanguageProfile` exists at all, so `resolve_media_file_profile` returns `None`
    — the breakdown falls back to the "no profile" label instead of crashing."""
    movie = _movie(in_memory_session, tmp_path)
    media_file = _media_file(in_memory_session, movie)
    subtitle = _subtitle(in_memory_session, media_file, "en")
    assert subtitle.id is not None
    in_memory_session.add(
        AcquisitionAttempt(
            subtitle_id=subtitle.id,
            provider="subdl",
            release_name="Foo",
            download_id="1",
            score=0.5,
            title_similarity=0.5,
            attempted_at=datetime.now(UTC),
        )
    )
    in_memory_session.commit()

    result = compute_statistics(in_memory_session)

    assert result.acquired.by_profile == [BreakdownEntry(label="—", count=1)]
