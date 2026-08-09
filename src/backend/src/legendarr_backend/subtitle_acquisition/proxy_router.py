from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.http_client.client import ProviderClientError, ProviderHttpClient
from legendarr_backend.subtitle_acquisition.manage_subtitle_proxy import (
    create_subtitle_proxy,
    delete_subtitle_proxy,
    get_subtitle_proxy,
    list_subtitle_proxies,
    set_subtitle_proxy_enabled,
    update_subtitle_proxy,
)
from legendarr_backend.subtitle_acquisition.models import SubtitleProxy
from legendarr_backend.subtitle_acquisition.schemas import (
    SubtitleProxyEnabledInput,
    SubtitleProxyInput,
    SubtitleProxyRead,
)

router = APIRouter(prefix="/subtitle-proxies")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _probe_connection(data: SubtitleProxyInput) -> tuple[bool, str]:
    """Bare reachability check — a proxy has no credential to validate, so this only
    confirms the host answers, same as `subtitle_acquisition/connection_tests.py`'s
    `_reachability_only`."""
    client = ProviderHttpClient(data.name, data.host)
    try:
        client.ping("/")
    except ProviderClientError as exc:
        return False, str(exc)
    finally:
        client.close()
    return True, "Connection successful"


def _require_reachable(data: SubtitleProxyInput) -> None:
    """Reject saving a proxy we can't reach."""
    success, message = _probe_connection(data)
    if not success:
        raise HTTPException(status_code=422, detail=message)


@router.get("/", response_model=list[SubtitleProxyRead])
def list_proxies(session: Session = Depends(_get_session)) -> list[SubtitleProxy]:
    return list_subtitle_proxies(session)


@router.post("/", response_model=SubtitleProxyRead, status_code=201)
def create_proxy(
    data: SubtitleProxyInput, session: Session = Depends(_get_session)
) -> SubtitleProxy:
    _require_reachable(data)
    try:
        return create_subtitle_proxy(session, data)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A proxy with this name already exists"
        ) from exc


@router.get("/{proxy_id}", response_model=SubtitleProxyRead)
def get_proxy(proxy_id: int, session: Session = Depends(_get_session)) -> SubtitleProxy:
    proxy = get_subtitle_proxy(session, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Subtitle proxy not found")
    return proxy


@router.put("/{proxy_id}", response_model=SubtitleProxyRead)
def update_proxy(
    proxy_id: int, data: SubtitleProxyInput, session: Session = Depends(_get_session)
) -> SubtitleProxy:
    existing = get_subtitle_proxy(session, proxy_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Subtitle proxy not found")
    _require_reachable(data)
    try:
        proxy = update_subtitle_proxy(session, proxy_id, data)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409, detail="A proxy with this name already exists"
        ) from exc
    if proxy is None:
        raise HTTPException(status_code=404, detail="Subtitle proxy not found")
    return proxy


@router.patch("/{proxy_id}/enabled", response_model=SubtitleProxyRead)
def set_proxy_enabled(
    proxy_id: int,
    data: SubtitleProxyEnabledInput,
    session: Session = Depends(_get_session),
) -> SubtitleProxy:
    # No reachability probe here — you should be able to disable an already-unreachable
    # proxy, and re-enabling shouldn't be gated on the box being up at that instant.
    proxy = set_subtitle_proxy_enabled(session, proxy_id, data.enabled)
    if proxy is None:
        raise HTTPException(status_code=404, detail="Subtitle proxy not found")
    return proxy


@router.delete("/{proxy_id}", status_code=204)
def delete_proxy(proxy_id: int, session: Session = Depends(_get_session)) -> None:
    if not delete_subtitle_proxy(session, proxy_id):
        raise HTTPException(status_code=404, detail="Subtitle proxy not found")


@router.post("/test")
def test_proxy(data: SubtitleProxyInput) -> dict:
    success, message = _probe_connection(data)
    return {"success": success, "message": message}
