from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from legendarr_backend.subtitle_acquisition.models import (
    SUBTITLE_PROVIDER_KINDS,
    SubtitleProviderConfig,
)
from legendarr_backend.subtitle_acquisition.schemas import SubtitleProviderConfigInput


def ensure_subtitle_providers_seeded(session: Session) -> None:
    """Insert a row for any provider kind not yet in the table, so the catalog always has
    exactly one row per `SUBTITLE_PROVIDER_KINDS` entry. Safe to call on every startup —
    existing rows (and their credentials) are left untouched. New rows seed `enabled=False`
    — nothing has credentials or a confirmed "Test connection" yet, so nothing should be on
    by default; the user opts in per provider from the web UI.
    """
    existing_kinds = set(session.exec(select(SubtitleProviderConfig.kind)).all())
    for kind in SUBTITLE_PROVIDER_KINDS:
        if kind not in existing_kinds:
            session.add(SubtitleProviderConfig(kind=kind, enabled=False))
    session.commit()


def list_subtitle_providers(session: Session) -> list[SubtitleProviderConfig]:
    return list(session.exec(select(SubtitleProviderConfig)).all())


def get_subtitle_provider(session: Session, provider_id: int) -> SubtitleProviderConfig | None:
    return session.get(SubtitleProviderConfig, provider_id)


def mark_connection_verified(session: Session, provider: SubtitleProviderConfig) -> None:
    """Record that a "Test connection" for this provider has succeeded at least once. Only
    ever set — a later failed test doesn't clear it, since the gate this backs
    (`SubtitleProviderConfig.is_configured`) only asks "has this ever worked," not "is it
    working right now." Only consulted by `is_configured` for kinds with no credential
    concept; credentialed kinds gate on `has_credentials` instead, so for those this is
    just bookkeeping.
    """
    if provider.connection_verified:
        return
    provider.connection_verified = True
    session.add(provider)
    session.commit()


def update_subtitle_provider(
    session: Session, provider_id: int, data: SubtitleProviderConfigInput
) -> SubtitleProviderConfig | None:
    provider = session.get(SubtitleProviderConfig, provider_id)
    if provider is None:
        return None
    for field, value in data.model_dump().items():
        setattr(provider, field, value)
    # Force the encrypted fields into the UPDATE even when unchanged, so a legacy plaintext
    # value read back by EncryptedString is re-encrypted on any edit, not just key rotations.
    flag_modified(provider, "api_key")
    flag_modified(provider, "password")
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider
