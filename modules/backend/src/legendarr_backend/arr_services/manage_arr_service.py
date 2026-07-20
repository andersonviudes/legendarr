from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, delete, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.media_library.models import Movie, Series


def create_arr_service(session: Session, data: ArrServiceInput) -> ArrService:
    service = ArrService.model_validate(data.model_dump())
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def list_arr_services(session: Session) -> list[ArrService]:
    return list(session.exec(select(ArrService)).all())


def list_enabled_arr_services(session: Session) -> list[ArrService]:
    return list(session.exec(select(ArrService).where(ArrService.enabled)).all())


def get_arr_service(session: Session, service_id: int) -> ArrService | None:
    return session.get(ArrService, service_id)


def update_arr_service(
    session: Session, service_id: int, data: ArrServiceInput
) -> ArrService | None:
    service = session.get(ArrService, service_id)
    if service is None:
        return None
    # service_type is fixed at creation — ignore whatever the caller sent for it.
    for field, value in data.model_dump(exclude={"service_type"}).items():
        setattr(service, field, value)
    # Force api_key into the UPDATE even when unchanged, so a legacy plaintext value
    # read back by EncryptedString is re-encrypted on any edit, not just key rotations.
    flag_modified(service, "api_key")
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def set_arr_service_enabled(session: Session, service_id: int, enabled: bool) -> ArrService | None:
    service = session.get(ArrService, service_id)
    if service is None:
        return None
    service.enabled = enabled
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def delete_arr_service(session: Session, service_id: int) -> bool:
    service = session.get(ArrService, service_id)
    if service is None:
        return False
    # SQLite runs with FK enforcement off by default, so the database won't cascade
    # for us — remove the connection's synced media explicitly instead of orphaning it.
    for model in (Movie, Series):
        session.exec(delete(model).where(model.arr_service_id == service_id))
    session.delete(service)
    session.commit()
    return True
