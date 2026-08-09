from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from legendarr_backend.media_metadata.models import (
    MEDIA_METADATA_PROVIDER_KINDS,
    MetadataProviderConfig,
)
from legendarr_backend.media_metadata.schemas import MetadataProviderConfigInput


def ensure_metadata_providers_seeded(session: Session) -> None:
    """Insert a row for any provider kind not yet in the table, so the catalog always has
    exactly one row per `MEDIA_METADATA_PROVIDER_KINDS` entry. Safe to call on every
    startup — existing rows (and their credentials) are left untouched. Unlike
    `ensure_subtitle_providers_seeded`, new rows seed `enabled=True` (the model's
    default) — the user asked for both sources on by default; what actually gates a
    fetch attempt is `has_credentials`, not this flag.
    """
    existing_kinds = set(session.exec(select(MetadataProviderConfig.kind)).all())
    for kind in MEDIA_METADATA_PROVIDER_KINDS:
        if kind not in existing_kinds:
            session.add(MetadataProviderConfig(kind=kind))
    session.commit()


def list_metadata_providers(session: Session) -> list[MetadataProviderConfig]:
    return list(session.exec(select(MetadataProviderConfig)).all())


def get_metadata_provider(session: Session, provider_id: int) -> MetadataProviderConfig | None:
    return session.get(MetadataProviderConfig, provider_id)


def mark_connection_verified(session: Session, provider: MetadataProviderConfig) -> None:
    if provider.connection_verified:
        return
    provider.connection_verified = True
    session.add(provider)
    session.commit()


def update_metadata_provider(
    session: Session, provider_id: int, data: MetadataProviderConfigInput
) -> MetadataProviderConfig | None:
    provider = session.get(MetadataProviderConfig, provider_id)
    if provider is None:
        return None
    for field, value in data.model_dump().items():
        setattr(provider, field, value)
    # Force the encrypted field into the UPDATE even when unchanged, so a legacy
    # plaintext value read back by EncryptedString is re-encrypted on any edit.
    flag_modified(provider, "api_key")
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider
