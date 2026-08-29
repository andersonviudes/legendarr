from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition import download_pending_subtitle as download_module
from legendarr_backend.subtitle_acquisition.download_pending_subtitle import (
    download_pending_subtitle_candidate,
)
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.search_media_file_subtitle import SubtitleCandidate
from sqlmodel import select


class _FakeProvider:
    def __init__(self, name: str, text: str = "1\n00:00:00,000 --> 00:00:15,000\nHi\n\n"):
        self.name = name
        self.text = text

    def search(self, *args, **kwargs):
        raise NotImplementedError

    def download(self, result):
        return self.text


class _FailingDownloadProvider:
    name = "failing"

    def search(self, *args, **kwargs):
        raise NotImplementedError

    def download(self, result):
        raise RuntimeError("boom")


def _series(session) -> Series:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name="sonarr", service_type="sonarr", host="sonarr", port=8989, api_key="api-key"
        ),
    )
    assert service.id is not None
    series = Series(
        arr_service_id=service.id, arr_id=7, title="Ahsoka", remote_path="/remote/Ahsoka"
    )
    session.add(series)
    session.commit()
    return series


def _use_chain(monkeypatch, *providers):
    monkeypatch.setattr(
        download_module, "resolve_subtitle_provider_chain", lambda session: list(providers)
    )


def _candidate(**overrides) -> SubtitleCandidate:
    data = {
        "provider": "provider",
        "release_name": "Ahsoka.S01E04",
        "download_id": "1",
        "language": "en",
        "page_link": None,
    }
    data.update(overrides)
    return SubtitleCandidate(**data)


def test_download_stages_a_pending_subtitle(in_memory_session, monkeypatch):
    series = _series(in_memory_session)
    _use_chain(monkeypatch, _FakeProvider("provider"))

    success, message = download_pending_subtitle_candidate(
        in_memory_session, series, 1, 4, _candidate(), "en"
    )

    assert success is True
    rows = in_memory_session.exec(
        select(PendingSubtitle).where(PendingSubtitle.series_id == series.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].season_number == 1
    assert rows[0].episode_number == 4
    assert rows[0].language == "en"
    assert b"Hi" in rows[0].content
    assert rows[0].provider == "provider"
    assert rows[0].download_id == "1"


def test_download_replaces_an_existing_pending_subtitle_for_the_same_episode_and_language(
    in_memory_session, monkeypatch
):
    series = _series(in_memory_session)
    first_text = "1\n00:00:00,000 --> 00:00:15,000\nFirst\n\n"
    second_text = "1\n00:00:00,000 --> 00:00:15,000\nSecond\n\n"
    _use_chain(monkeypatch, _FakeProvider("provider", text=first_text))
    download_pending_subtitle_candidate(in_memory_session, series, 1, 4, _candidate(), "en")

    _use_chain(monkeypatch, _FakeProvider("provider", text=second_text))
    download_pending_subtitle_candidate(
        in_memory_session, series, 1, 4, _candidate(download_id="2"), "en"
    )

    rows = in_memory_session.exec(
        select(PendingSubtitle).where(PendingSubtitle.series_id == series.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].content == second_text.encode("utf-8")
    assert rows[0].download_id == "2"


def test_download_returns_false_when_the_provider_is_no_longer_in_the_chain(
    in_memory_session, monkeypatch
):
    series = _series(in_memory_session)
    _use_chain(monkeypatch, _FakeProvider("some-other-provider"))

    success, message = download_pending_subtitle_candidate(
        in_memory_session, series, 1, 4, _candidate(provider="gone"), "en"
    )

    assert success is False
    assert in_memory_session.exec(select(PendingSubtitle)).all() == []


def test_download_returns_false_on_a_provider_exception(in_memory_session, monkeypatch):
    series = _series(in_memory_session)
    _use_chain(monkeypatch, _FailingDownloadProvider())

    success, message = download_pending_subtitle_candidate(
        in_memory_session, series, 1, 4, _candidate(provider="failing"), "en"
    )

    assert success is False
    assert in_memory_session.exec(select(PendingSubtitle)).all() == []


def test_download_returns_false_when_the_content_fails_the_quality_gate(
    in_memory_session, monkeypatch
):
    series = _series(in_memory_session)
    _use_chain(monkeypatch, _FakeProvider("provider", text="too short to be a real subtitle"))

    success, message = download_pending_subtitle_candidate(
        in_memory_session, series, 1, 4, _candidate(), "en"
    )

    assert success is False
    assert in_memory_session.exec(select(PendingSubtitle)).all() == []
