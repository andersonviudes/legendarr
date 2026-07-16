from sqlmodel import Session, select

from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import ArrServiceInput


def create_arr_service(session: Session, data: ArrServiceInput) -> ArrService:
    service = ArrService.model_validate(data.model_dump())
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def list_arr_services(session: Session) -> list[ArrService]:
    return list(session.exec(select(ArrService)).all())


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
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def delete_arr_service(session: Session, service_id: int) -> bool:
    service = session.get(ArrService, service_id)
    if service is None:
        return False
    session.delete(service)
    session.commit()
    return True
