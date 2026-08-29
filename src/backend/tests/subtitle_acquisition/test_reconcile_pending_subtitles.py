from datetime import UTC, datetime
from pathlib import Path

from legendarr_backend.arr_clients.base import EpisodeItem
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.http_client.client import ProviderClientError
from legendarr_backend.media_library.models import MediaFile, Series
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.reconcile_pending_subtitles import (
    reconcile_pending_subtitles_for_series,
)
from legendarr_backend.subtitle_discovery.models import Subtitle
from sqlmodel import select


def _series(session, tmp_path: Path) -> Series:
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
    assert service.id is not None
    series = Series(
        arr_service_id=service.id, arr_id=7, title="Ahsoka", remote_path="/remote/Ahsoka"
    )
    session.add(series)
    session.commit()
    return series


def _pending(session, series: Series, **overrides) -> PendingSubtitle:
    data = {
        "series_id": series.id,
        "season_number": 1,
        "episode_number": 4,
        "language": "en",
        "filename": "en.srt",
        "content": b"pending content",
        "provider": "provider",
        "release_name": "Ahsoka.S01E04",
        "download_id": "1",
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    pending = PendingSubtitle(**data)
    session.add(pending)
    session.commit()
    return pending


class _FakeClient:
    def __init__(self, episodes):
        self.episodes = episodes

    def list_episodes(self, series_id):
        return self.episodes

    def close(self):
        pass


class _UnreachableClient:
    def list_episodes(self, series_id):
        raise ProviderClientError("sonarr request timed out")

    def close(self):
        pass


def _use_client(monkeypatch, client):
    monkeypatch.setattr(
        "legendarr_backend.subtitle_acquisition.reconcile_pending_subtitles.build_client",
        lambda arr_service: client,
    )


def test_reconcile_returns_zero_without_calling_sonarr_when_nothing_is_pending(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path)
    assert series.id is not None

    class _ExplodingClient:
        def list_episodes(self, series_id):
            raise AssertionError("shouldn't be called")

        def close(self):
            pass

    _use_client(monkeypatch, _ExplodingClient())

    assert reconcile_pending_subtitles_for_series(in_memory_session, series.id) == 0


def test_reconcile_materializes_a_pending_subtitle_onto_the_now_downloaded_episode(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path)
    assert series.id is not None
    _pending(in_memory_session, series)
    # `series.remote_path` ("/remote/Ahsoka") already maps to `tmp_path / "Ahsoka"` (the
    # connection's remote/local prefix pair) — `relative_path` is relative to *that* root,
    # not the series root's own name again.
    video = tmp_path / "Ahsoka" / "Ahsoka.S01E04.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Ahsoka.S01E04.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    _use_client(
        monkeypatch,
        _FakeClient(
            [
                EpisodeItem(
                    season_number=1,
                    episode_number=4,
                    title="Fallen Jedi",
                    relative_path="Ahsoka.S01E04.mkv",
                )
            ]
        ),
    )

    materialized = reconcile_pending_subtitles_for_series(in_memory_session, series.id)

    assert materialized == 1
    assert (video.with_name("Ahsoka.S01E04.en.srt")).read_bytes() == b"pending content"
    assert in_memory_session.exec(select(PendingSubtitle)).all() == []
    subtitles = in_memory_session.exec(
        select(Subtitle).where(Subtitle.media_file_id == media_file.id)
    ).all()
    assert any(row.language == "en" for row in subtitles)


def test_reconcile_lowercases_the_language_in_the_written_filename(
    in_memory_session, tmp_path, monkeypatch
):
    # `pending.language` keeps its target-language casing ("pt-BR", see
    # download_pending_subtitle/upload_pending_subtitle), but the on-disk filename
    # segment always lowercases it, matching every other subtitle-writing path.
    series = _series(in_memory_session, tmp_path)
    assert series.id is not None
    _pending(in_memory_session, series, language="pt-BR", filename="pt-br.srt")
    video = tmp_path / "Ahsoka" / "Ahsoka.S01E04.mkv"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.touch()
    media_file = MediaFile(
        series_id=series.id,
        relative_path="Ahsoka.S01E04.mkv",
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    in_memory_session.add(media_file)
    in_memory_session.commit()
    _use_client(
        monkeypatch,
        _FakeClient(
            [
                EpisodeItem(
                    season_number=1,
                    episode_number=4,
                    title="Fallen Jedi",
                    relative_path="Ahsoka.S01E04.mkv",
                )
            ]
        ),
    )

    materialized = reconcile_pending_subtitles_for_series(in_memory_session, series.id)

    assert materialized == 1
    assert (video.with_name("Ahsoka.S01E04.pt-br.srt")).read_bytes() == b"pending content"


def test_reconcile_leaves_a_pending_subtitle_alone_when_the_episode_still_has_no_file(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path)
    assert series.id is not None
    _pending(in_memory_session, series)
    _use_client(monkeypatch, _FakeClient([]))

    materialized = reconcile_pending_subtitles_for_series(in_memory_session, series.id)

    assert materialized == 0
    assert len(in_memory_session.exec(select(PendingSubtitle)).all()) == 1


def test_reconcile_returns_zero_when_sonarr_is_unreachable(
    in_memory_session, tmp_path, monkeypatch
):
    series = _series(in_memory_session, tmp_path)
    assert series.id is not None
    _pending(in_memory_session, series)
    _use_client(monkeypatch, _UnreachableClient())

    materialized = reconcile_pending_subtitles_for_series(in_memory_session, series.id)

    assert materialized == 0
    assert len(in_memory_session.exec(select(PendingSubtitle)).all()) == 1
