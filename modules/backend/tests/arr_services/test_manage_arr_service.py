from legendarr_backend.arr_services.manage_arr_service import (
    create_arr_service,
    delete_arr_service,
    get_arr_service,
    list_arr_services,
    update_arr_service,
)
from legendarr_backend.arr_services.schemas import ArrServiceInput


def _radarr_input(**overrides) -> ArrServiceInput:
    data = {
        "name": "radarr",
        "service_type": "radarr",
        "host": "radarr",
        "port": 7878,
        "api_key": "api-key",
    }
    data.update(overrides)
    return ArrServiceInput(**data)


def test_create_and_list_arr_service(in_memory_session):
    create_arr_service(in_memory_session, _radarr_input())

    services = list_arr_services(in_memory_session)

    assert [service.name for service in services] == ["radarr"]


def test_get_arr_service_returns_none_when_missing(in_memory_session):
    assert get_arr_service(in_memory_session, 1) is None


def test_update_arr_service_replaces_fields(in_memory_session):
    service = create_arr_service(in_memory_session, _radarr_input())

    updated = update_arr_service(
        in_memory_session, service.id, _radarr_input(host="radarr.internal", port=7879)
    )

    assert updated.host == "radarr.internal"
    assert updated.port == 7879


def test_update_arr_service_ignores_service_type_change(in_memory_session):
    service = create_arr_service(in_memory_session, _radarr_input())

    updated = update_arr_service(
        in_memory_session, service.id, _radarr_input(service_type="sonarr")
    )

    assert updated.service_type == "radarr"


def test_update_arr_service_returns_none_when_missing(in_memory_session):
    assert update_arr_service(in_memory_session, 1, _radarr_input()) is None


def test_delete_arr_service(in_memory_session):
    service = create_arr_service(in_memory_session, _radarr_input())

    assert delete_arr_service(in_memory_session, service.id) is True
    assert list_arr_services(in_memory_session) == []


def test_delete_arr_service_returns_false_when_missing(in_memory_session):
    assert delete_arr_service(in_memory_session, 1) is False
