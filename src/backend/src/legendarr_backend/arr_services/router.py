from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from legendarr_backend.arr_services.client_factory import build_client
from legendarr_backend.arr_services.manage_arr_service import (
    create_arr_service,
    delete_arr_service,
    get_arr_service,
    list_arr_services,
    set_arr_service_enabled,
    update_arr_service,
)
from legendarr_backend.arr_services.models import ArrService
from legendarr_backend.arr_services.schemas import (
    ArrServiceEnabledInput,
    ArrServiceInput,
    ArrServiceRead,
)
from legendarr_backend.database.engine import get_session
from legendarr_backend.http_client.client import ProviderClientError, describe_error

router = APIRouter(prefix="/arr-services")

# The `appName` field Radarr/Sonarr report on `/api/v3/system/status`. Both apps share
# the same status endpoint, so this is what tells a Radarr instance apart from a Sonarr one.
_APP_NAME_BY_TYPE = {"radarr": "Radarr", "sonarr": "Sonarr"}


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _probe_connection(data: ArrServiceInput) -> tuple[bool, str]:
    """Ping the arr server and confirm it's the expected app.

    Returns `(success, message)` — a failure covers both an unreachable server and one
    that answers but turns out to be the other app (e.g. a Sonarr behind a Radarr config).
    """
    client = build_client(data)
    try:
        status = client.system_status()
    except ProviderClientError as exc:
        return False, describe_error(exc)
    finally:
        client.close()

    expected = _APP_NAME_BY_TYPE.get(data.service_type, data.service_type)
    actual = status.get("appName") or "an unknown app"
    if actual != expected:
        return False, f"Connected, but this is {actual}, not {expected}"
    version = status.get("version")
    detail = f"{expected} {version}".strip() if version else expected
    return True, f"Connection successful — {detail}"


def _require_reachable(data: ArrServiceInput) -> None:
    """Reject saving a service we can't reach or that isn't the expected app."""
    success, message = _probe_connection(data)
    if not success:
        raise HTTPException(status_code=422, detail=message)


@router.get("/", response_model=list[ArrServiceRead])
def list_services(session: Session = Depends(_get_session)) -> list[ArrService]:
    return list_arr_services(session)


@router.post("/", response_model=ArrServiceRead, status_code=201)
def create_service(data: ArrServiceInput, session: Session = Depends(_get_session)) -> ArrService:
    if not data.api_key:
        raise HTTPException(status_code=422, detail="API Key is required")
    _require_reachable(data)
    try:
        return create_arr_service(session, data)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="An arr service with this name already exists"
        ) from exc


@router.get("/{service_id}", response_model=ArrServiceRead)
def get_service(service_id: int, session: Session = Depends(_get_session)) -> ArrService:
    service = get_arr_service(session, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    return service


@router.put("/{service_id}", response_model=ArrServiceRead)
def update_service(
    service_id: int, data: ArrServiceInput, session: Session = Depends(_get_session)
) -> ArrService:
    existing = get_arr_service(session, service_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    # A blank api_key means "keep the current one" — the edit form never re-displays the
    # stored key, so an unchanged edit submits it empty. Fill it in before probing/saving.
    if not data.api_key:
        data = data.model_copy(update={"api_key": existing.api_key})
    _require_reachable(data)
    try:
        service = update_arr_service(session, service_id, data)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="An arr service with this name already exists"
        ) from exc
    if service is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    return service


@router.patch("/{service_id}/enabled", response_model=ArrServiceRead)
def set_service_enabled(
    service_id: int,
    data: ArrServiceEnabledInput,
    session: Session = Depends(_get_session),
) -> ArrService:
    # No reachability probe here — you should be able to disable an already-unreachable
    # server, and re-enabling shouldn't be gated on the box being up at that instant.
    service = set_arr_service_enabled(session, service_id, data.enabled)
    if service is None:
        raise HTTPException(status_code=404, detail="Arr service not found")
    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, session: Session = Depends(_get_session)) -> None:
    if not delete_arr_service(session, service_id):
        raise HTTPException(status_code=404, detail="Arr service not found")


@router.post("/test")
def test_service(data: ArrServiceInput) -> dict:
    success, message = _probe_connection(data)
    return {"success": success, "message": message}
