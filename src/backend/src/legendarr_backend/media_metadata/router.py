from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from legendarr_backend.config.config_file import load_or_create_config_file
from legendarr_backend.config.settings import get_settings
from legendarr_backend.database.engine import get_session
from legendarr_backend.media_metadata.connection_tests import test_connection
from legendarr_backend.media_metadata.jobs import enqueue_metadata_refetch
from legendarr_backend.media_metadata.manage_metadata_provider import (
    get_metadata_provider,
    list_metadata_providers,
    mark_connection_verified,
    update_metadata_provider,
)
from legendarr_backend.media_metadata.models import MetadataProviderConfig
from legendarr_backend.media_metadata.schemas import (
    MetadataProviderConfigInput,
    MetadataProviderConfigRead,
)

router = APIRouter(prefix="/metadata-providers", tags=["Metadata Providers"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _merge_with_existing(
    data: MetadataProviderConfigInput, existing: MetadataProviderConfig
) -> MetadataProviderConfigInput:
    """A blank secret means "keep the current one"; a field the request never sent at
    all means "don't touch it" — same reasoning as `subtitle_acquisition/router.py`."""
    provided = data.model_fields_set
    return data.model_copy(
        update={
            "enabled": data.enabled if "enabled" in provided else existing.enabled,
            "api_key": data.api_key or existing.api_key,
        }
    )


@router.get("/", response_model=list[MetadataProviderConfigRead])
def list_providers(session: Session = Depends(_get_session)) -> list[MetadataProviderConfig]:
    return list_metadata_providers(session)


@router.get("/{provider_id}", response_model=MetadataProviderConfigRead)
def get_provider(
    provider_id: int, session: Session = Depends(_get_session)
) -> MetadataProviderConfig:
    provider = get_metadata_provider(session, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Metadata provider not found")
    return provider


@router.patch("/{provider_id}", response_model=MetadataProviderConfigRead)
def update_provider(
    provider_id: int,
    data: MetadataProviderConfigInput,
    session: Session = Depends(_get_session),
) -> MetadataProviderConfig:
    existing = get_metadata_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Metadata provider not found")
    provider = update_metadata_provider(session, provider_id, _merge_with_existing(data, existing))
    assert provider is not None
    return provider


@router.post("/{provider_id}/test")
def test_provider_connection(
    provider_id: int,
    data: MetadataProviderConfigInput,
    session: Session = Depends(_get_session),
) -> dict:
    existing = get_metadata_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Metadata provider not found")
    merged = _merge_with_existing(data, existing)
    candidate = existing.model_copy(update=merged.model_dump())
    success, message = test_connection(candidate)
    if success:
        mark_connection_verified(session, existing)
    return {"success": success, "message": message}


@router.post("/refetch", status_code=202)
def trigger_metadata_refetch(
    request: Request, session: Session = Depends(_get_session)
) -> dict[str, int]:
    """Enqueue a metadata refetch for every existing movie/series — same shape as
    `media_library`'s manual full-library scan trigger."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler is not running")
    config = load_or_create_config_file(get_settings())
    movies, series = enqueue_metadata_refetch(
        scheduler,
        session,
        retry_attempts=config.metadata_refetch_retry_attempts,
        retry_delay_seconds=config.metadata_refetch_retry_delay_seconds,
    )
    return {"movies_enqueued": movies, "series_enqueued": series}
