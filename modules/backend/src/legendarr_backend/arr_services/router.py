from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.manage_arr_service import (
    create_arr_service,
    delete_arr_service,
    get_arr_service,
    list_arr_services,
    update_arr_service,
)
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import ArrServiceInput
from legendarr_backend.database.engine import get_session
from legendarr_backend.http_client.client import ProviderClientError

router = APIRouter(prefix="/arr-services")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


@router.get("/", response_model=list[ArrService])
def list_services(session: Session = Depends(_get_session)) -> list[ArrService]:
    return list_arr_services(session)


@router.post("/", response_model=ArrService, status_code=201)
def create_service(data: ArrServiceInput, session: Session = Depends(_get_session)) -> ArrService:
    return create_arr_service(session, data)


@router.get("/{service_id}", response_model=ArrService)
def get_service(service_id: int, session: Session = Depends(_get_session)) -> ArrService:
    service = get_arr_service(session, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    return service


@router.put("/{service_id}", response_model=ArrService)
def update_service(
    service_id: int, data: ArrServiceInput, session: Session = Depends(_get_session)
) -> ArrService:
    service = update_arr_service(session, service_id, data)
    if service is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, session: Session = Depends(_get_session)) -> None:
    if not delete_arr_service(session, service_id):
        raise HTTPException(status_code=404, detail="Arr service not found")


@router.post("/test")
def test_service(data: ArrServiceInput) -> dict:
    client = build_client(data)
    try:
        client.ping()
    except ProviderClientError as exc:
        return {"success": False, "message": str(exc)}
    finally:
        client.close()
    return {"success": True, "message": "Connection successful"}
