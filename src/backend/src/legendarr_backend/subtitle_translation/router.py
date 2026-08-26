from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from legendarr_backend.database.engine import get_session
from legendarr_backend.subtitle_translation.connection_tests import test_connection
from legendarr_backend.subtitle_translation.manage_translation_provider import (
    get_translation_provider,
    list_translation_providers,
    mark_connection_verified,
    update_translation_provider,
)
from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.schemas import (
    TranslationProviderConfigInput,
    TranslationProviderConfigRead,
)

router = APIRouter(prefix="/translation-providers", tags=["Translation Providers"])


def _get_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _merge_with_existing(
    data: TranslationProviderConfigInput, existing: TranslationProviderConfig
) -> TranslationProviderConfigInput:
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
            "api_key": data.api_key or existing.api_key,
            "endpoint": data.endpoint if "endpoint" in provided else existing.endpoint,
            "model": data.model if "model" in provided else existing.model,
            "prompt_template": (
                data.prompt_template if "prompt_template" in provided else existing.prompt_template
            ),
        }
    )


def _validate_prompt_template(prompt_template: str | None) -> None:
    """A blank template means "use the provider's default" and needs no validation.
    A non-blank one must round-trip the same `.format(source=..., target=..., count=...)`
    call `LLMTranslationProvider.translate_batch` makes — catch a bad placeholder here
    instead of failing silently at translate time (ROADMAP.md 0.9.0)."""
    if not prompt_template:
        return
    try:
        prompt_template.format(source="en", target="pt-BR", count=1)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid prompt template: {exc}") from exc


@router.get("/", response_model=list[TranslationProviderConfigRead])
def list_providers(session: Session = Depends(_get_session)) -> list[TranslationProviderConfig]:
    return list_translation_providers(session)


@router.get("/{provider_id}", response_model=TranslationProviderConfigRead)
def get_provider(
    provider_id: int, session: Session = Depends(_get_session)
) -> TranslationProviderConfig:
    provider = get_translation_provider(session, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Translation provider not found")
    return provider


@router.patch("/{provider_id}", response_model=TranslationProviderConfigRead)
def update_provider(
    provider_id: int,
    data: TranslationProviderConfigInput,
    session: Session = Depends(_get_session),
) -> TranslationProviderConfig:
    existing = get_translation_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Translation provider not found")
    merged = _merge_with_existing(data, existing)
    _validate_prompt_template(merged.prompt_template)
    provider = update_translation_provider(session, provider_id, merged)
    assert provider is not None
    return provider


@router.post("/{provider_id}/test")
def test_provider_connection(
    provider_id: int,
    data: TranslationProviderConfigInput,
    session: Session = Depends(_get_session),
) -> dict:
    existing = get_translation_provider(session, provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Translation provider not found")
    merged = _merge_with_existing(data, existing)
    candidate = existing.model_copy(update=merged.model_dump())
    success, message = test_connection(candidate)
    if success:
        mark_connection_verified(session, existing)
    return {"success": success, "message": message}
