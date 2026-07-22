from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.subtitle_acquisition.connection_tests import test_connection
from legendarr_backend.subtitle_acquisition.manage_subtitle_provider import (
    get_subtitle_provider,
    list_subtitle_providers,
    mark_connection_verified,
    update_subtitle_provider,
)
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.schemas import (
    SubtitleProviderConfigInput,
    SubtitleProviderConfigRead,
)

router = APIRouter(prefix="/subtitle-providers")


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _merge_with_existing(
    data: SubtitleProviderConfigInput, existing: SubtitleProviderConfig
) -> SubtitleProviderConfigInput:
    """A blank secret means "keep the current one" — the edit form never re-displays a
    stored secret, so an unchanged edit submits it empty. A field the request never sent
    at all — `enabled` from the edit form, everything but `enabled` from the toggle route
    — means "don't touch it," so fall back to what's already stored rather than the
    schema's bare default.
    """
    provided = data.model_fields_set
    return data.model_copy(
        update={
            "enabled": data.enabled if "enabled" in provided else existing.enabled,
            "username": data.username if "username" in provided else existing.username,
            "api_key": data.api_key or existing.api_key,
            "password": data.password or existing.password,
            "proxy_id": data.proxy_id if "proxy_id" in provided else existing.proxy_id,
            "use_hash": data.use_hash if "use_hash" in provided else existing.use_hash,
            "include_ai_translated": data.include_ai_translated
            if "include_ai_translated" in provided
            else existing.include_ai_translated,
            "include_machine_translated": data.include_machine_translated
            if "include_machine_translated" in provided
            else existing.include_machine_translated,
        }
    )


@router.get("/", response_model=list[SubtitleProviderConfigRead])
def list_providers(session: Session = Depends(_get_session)) -> list[SubtitleProviderConfig]:
    return list_subtitle_providers(session)


@router.get("/{provider_id}", response_model=SubtitleProviderConfigRead)
def get_provider(
    provider_id: int, session: Session = Depends(_get_session)
) -> SubtitleProviderConfig:
    provider = get_subtitle_provider(session, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Subtitle provider not found")
    return provider


@router.patch("/{provider_id}", response_model=SubtitleProviderConfigRead)
def update_provider(
    provider_id: int,
    data: SubtitleProviderConfigInput,
    session: Session = Depends(_get_session),
) -> SubtitleProviderConfig:
    existing = get_subtitle_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Subtitle provider not found")
    provider = update_subtitle_provider(session, provider_id, _merge_with_existing(data, existing))
    return provider


@router.post("/{provider_id}/test")
def test_provider_connection(
    provider_id: int,
    data: SubtitleProviderConfigInput,
    session: Session = Depends(_get_session),
) -> dict:
    existing = get_subtitle_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Subtitle provider not found")
    merged = _merge_with_existing(data, existing)
    candidate = existing.model_copy(update=merged.model_dump())
    success, message = test_connection(candidate)
    if success:
        mark_connection_verified(session, existing)
    return {"success": success, "message": message}
