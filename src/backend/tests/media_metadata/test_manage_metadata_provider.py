from legendarr_backend.media_metadata.manage_metadata_provider import (
    ensure_metadata_providers_seeded,
    get_metadata_provider,
    list_metadata_providers,
    mark_connection_verified,
    update_metadata_provider,
)
from legendarr_backend.media_metadata.models import MEDIA_METADATA_PROVIDER_KINDS
from legendarr_backend.media_metadata.schemas import MetadataProviderConfigInput
from legendarr_backend.security.secrets import ENCRYPTED_PREFIX
from sqlalchemy import text


def test_ensure_metadata_providers_seeded_creates_one_row_per_kind(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)

    providers = list_metadata_providers(in_memory_session)

    assert {provider.kind for provider in providers} == set(MEDIA_METADATA_PROVIDER_KINDS)
    # Unlike subtitle providers, both kinds seed enabled — the user asked for both on
    # by default; what gates a real fetch is `has_credentials`, not this flag.
    assert all(provider.enabled for provider in providers)


def test_ensure_metadata_providers_seeded_is_idempotent(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)
    ensure_metadata_providers_seeded(in_memory_session)

    providers = list_metadata_providers(in_memory_session)

    assert len(providers) == len(MEDIA_METADATA_PROVIDER_KINDS)


def test_ensure_metadata_providers_seeded_keeps_existing_credentials(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)
    provider = next(p for p in list_metadata_providers(in_memory_session) if p.kind == "tvdb")
    assert provider.id is not None
    update_metadata_provider(
        in_memory_session, provider.id, MetadataProviderConfigInput(api_key="my-key")
    )

    ensure_metadata_providers_seeded(in_memory_session)

    refreshed = get_metadata_provider(in_memory_session, provider.id)
    assert refreshed is not None
    assert refreshed.api_key == "my-key"


def test_get_metadata_provider_returns_none_when_missing(in_memory_session):
    assert get_metadata_provider(in_memory_session, 1) is None


def test_mark_connection_verified_sets_the_flag(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)
    provider = list_metadata_providers(in_memory_session)[0]
    assert provider.id is not None

    mark_connection_verified(in_memory_session, provider)

    refreshed = get_metadata_provider(in_memory_session, provider.id)
    assert refreshed is not None
    assert refreshed.connection_verified is True


def test_update_metadata_provider_replaces_fields(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)
    provider = list_metadata_providers(in_memory_session)[0]
    assert provider.id is not None

    updated = update_metadata_provider(
        in_memory_session,
        provider.id,
        MetadataProviderConfigInput(enabled=False, api_key="secret-key"),
    )

    assert updated is not None
    assert updated.enabled is False
    assert updated.api_key == "secret-key"


def test_update_metadata_provider_returns_none_when_missing(in_memory_session):
    assert update_metadata_provider(in_memory_session, 1, MetadataProviderConfigInput()) is None


def test_secrets_are_encrypted_at_rest(in_memory_session):
    ensure_metadata_providers_seeded(in_memory_session)
    provider = list_metadata_providers(in_memory_session)[0]
    assert provider.id is not None

    update_metadata_provider(
        in_memory_session, provider.id, MetadataProviderConfigInput(api_key="secret-key")
    )

    row = in_memory_session.execute(
        text("SELECT api_key FROM metadataproviderconfig WHERE id = :id"), {"id": provider.id}
    ).one()

    assert row.api_key.startswith(ENCRYPTED_PREFIX)
    assert "secret-key" not in row.api_key
