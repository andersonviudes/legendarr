from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from legendarr_backend.subtitle_translation.models import (
    TRANSLATION_PROVIDER_KINDS,
    TranslationProviderConfig,
)
from legendarr_backend.subtitle_translation.schemas import TranslationProviderConfigInput


def ensure_translation_providers_seeded(session: Session) -> None:
    """Insert a row for any provider kind not yet in the table, so the catalog always has
    exactly one row per `TRANSLATION_PROVIDER_KINDS` entry. Safe to call on every startup —
    existing rows (and their credentials) are left untouched. New rows seed `enabled=False`
    — nothing has credentials or a confirmed "Test connection" yet, so nothing should be on
    by default; the user opts in per provider from the web UI.
    """
    existing_kinds = set(session.exec(select(TranslationProviderConfig.kind)).all())
    for kind in TRANSLATION_PROVIDER_KINDS:
        if kind not in existing_kinds:
            session.add(TranslationProviderConfig(kind=kind, enabled=False))
    session.commit()


def list_translation_providers(session: Session) -> list[TranslationProviderConfig]:
    return list(session.exec(select(TranslationProviderConfig)).all())


def get_translation_provider(
    session: Session, provider_id: int
) -> TranslationProviderConfig | None:
    return session.get(TranslationProviderConfig, provider_id)


def mark_connection_verified(session: Session, provider: TranslationProviderConfig) -> None:
    """Record that a "Test connection" for this provider has succeeded at least once. Only
    ever set — a later failed test doesn't clear it, mirroring
    `subtitle_acquisition.manage_subtitle_provider.mark_connection_verified`.
    """
    if provider.connection_verified:
        return
    provider.connection_verified = True
    session.add(provider)
    session.commit()


def update_translation_provider(
    session: Session, provider_id: int, data: TranslationProviderConfigInput
) -> TranslationProviderConfig | None:
    provider = session.get(TranslationProviderConfig, provider_id)
    if provider is None:
        return None
    for field, value in data.model_dump().items():
        setattr(provider, field, value)
    # Force the encrypted field into the UPDATE even when unchanged, so a legacy plaintext
    # value read back by EncryptedString is re-encrypted on any edit, not just key rotations.
    flag_modified(provider, "api_key")
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider
