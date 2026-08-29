import pytest
from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import Series
from legendarr_backend.subtitle_acquisition.models import PendingSubtitle
from legendarr_backend.subtitle_acquisition.upload_pending_subtitle import upload_pending_subtitle
from sqlmodel import select


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


@pytest.mark.parametrize("suffix", [".srt", ".ass", ".ssa", ".vtt"])
def test_upload_stages_a_pending_subtitle(in_memory_session, suffix):
    series = _series(in_memory_session)

    success, message = upload_pending_subtitle(
        in_memory_session, series, 1, 4, "en", f"uploaded{suffix}", b"content"
    )

    assert success is True
    rows = in_memory_session.exec(
        select(PendingSubtitle).where(PendingSubtitle.series_id == series.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].content == b"content"
    assert rows[0].filename == f"en{suffix}"
    assert rows[0].provider is None


def test_upload_rejects_a_disallowed_extension_without_staging_anything(in_memory_session):
    series = _series(in_memory_session)

    success, message = upload_pending_subtitle(
        in_memory_session, series, 1, 4, "en", "uploaded.txt", b"content"
    )

    assert success is False
    assert in_memory_session.exec(select(PendingSubtitle)).all() == []


def test_upload_replaces_an_existing_pending_subtitle_for_the_same_episode_and_language(
    in_memory_session,
):
    series = _series(in_memory_session)
    upload_pending_subtitle(in_memory_session, series, 1, 4, "en", "first.srt", b"first")

    upload_pending_subtitle(in_memory_session, series, 1, 4, "en", "second.srt", b"second")

    rows = in_memory_session.exec(
        select(PendingSubtitle).where(PendingSubtitle.series_id == series.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].content == b"second"
