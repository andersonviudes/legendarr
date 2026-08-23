from datetime import UTC, datetime

from legendarr_backend.arr_services.manage_arr_service import create_arr_service
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import MediaFile, Movie
from legendarr_backend.subtitle_acquisition.manage_subtitle_blacklist import (
    add_blacklist_entry,
    clear_translation_blacklist,
    is_translation_blacklisted,
    list_blacklisted_download_ids,
)


def _media_file(session, tmp_path, **overrides) -> MediaFile:
    service = create_arr_service(
        session,
        ArrServiceInput(
            name=f"radarr-{overrides.get('arr_id', 1)}",
            service_type="radarr",
            host="radarr",
            port=7878,
            api_key="api-key",
            remote_path_prefix="/remote",
            local_path_prefix=str(tmp_path),
        ),
    )
    data = {"arr_service_id": service.id, "arr_id": 1, "title": "Foo", "remote_path": "/remote/Foo"}
    data.update({k: v for k, v in overrides.items() if k != "relative_path"})
    movie = Movie(**data)
    session.add(movie)
    session.commit()
    media_file = MediaFile(
        movie_id=movie.id,
        relative_path=overrides.get("relative_path", "Foo/Foo.mkv"),
        size_bytes=1,
        scanned_at=datetime.now(UTC),
    )
    session.add(media_file)
    session.commit()
    return media_file


def test_list_blacklisted_download_ids_only_returns_acquired_entries_for_this_language(
    in_memory_session, tmp_path
):
    media_file = _media_file(in_memory_session, tmp_path, arr_id=1)
    other_media_file = _media_file(
        in_memory_session, tmp_path, arr_id=2, relative_path="Bar/Bar.mkv"
    )
    assert media_file.id is not None
    assert other_media_file.id is not None

    add_blacklist_entry(
        in_memory_session,
        media_file_id=media_file.id,
        language="en",
        origin="acquired",
        provider="fake",
        release_name="Foo",
        download_id="1",
    )
    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="en", origin="translated"
    )
    add_blacklist_entry(
        in_memory_session,
        media_file_id=media_file.id,
        language="ja",
        origin="acquired",
        provider="fake",
        release_name="Bar",
        download_id="2",
    )
    add_blacklist_entry(
        in_memory_session,
        media_file_id=other_media_file.id,
        language="en",
        origin="acquired",
        provider="fake",
        release_name="Baz",
        download_id="3",
    )
    in_memory_session.commit()

    assert list_blacklisted_download_ids(in_memory_session, media_file.id, "en") == {("fake", "1")}
    assert list_blacklisted_download_ids(in_memory_session, media_file.id, "EN") == {("fake", "1")}


def test_list_blacklisted_download_ids_empty_when_nothing_blacklisted(in_memory_session):
    assert list_blacklisted_download_ids(in_memory_session, 1, "en") == set()


def test_is_translation_blacklisted_true_only_for_a_translated_entry(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None
    add_blacklist_entry(
        in_memory_session,
        media_file_id=media_file.id,
        language="pt-BR",
        origin="acquired",
        provider="fake",
        release_name="Foo",
        download_id="1",
    )
    in_memory_session.commit()
    assert is_translation_blacklisted(in_memory_session, media_file.id, "pt-BR") is False

    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="pt-BR", origin="translated"
    )
    in_memory_session.commit()
    assert is_translation_blacklisted(in_memory_session, media_file.id, "pt-BR") is True


def test_clear_translation_blacklist_removes_only_matching_entries(in_memory_session, tmp_path):
    media_file = _media_file(in_memory_session, tmp_path)
    assert media_file.id is not None
    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="pt-BR", origin="translated"
    )
    add_blacklist_entry(
        in_memory_session, media_file_id=media_file.id, language="ja", origin="translated"
    )
    add_blacklist_entry(
        in_memory_session,
        media_file_id=media_file.id,
        language="pt-BR",
        origin="acquired",
        provider="fake",
        release_name="Foo",
        download_id="1",
    )
    in_memory_session.commit()

    clear_translation_blacklist(in_memory_session, media_file.id, "pt-BR")
    in_memory_session.commit()

    assert is_translation_blacklisted(in_memory_session, media_file.id, "pt-BR") is False
    assert is_translation_blacklisted(in_memory_session, media_file.id, "ja") is True
    # The "acquired" entry for the same media file/language is untouched.
    assert list_blacklisted_download_ids(in_memory_session, media_file.id, "pt-BR") == {
        ("fake", "1")
    }
