from legendarr_backend.security.secrets import ENCRYPTED_PREFIX
from legendarr_backend.subtitle_translation.manage_translation_provider import (
    ensure_translation_providers_seeded,
    get_translation_provider,
    list_translation_providers,
    mark_connection_verified,
    update_translation_provider,
)
from legendarr_backend.subtitle_translation.models import TRANSLATION_PROVIDER_KINDS
from legendarr_backend.subtitle_translation.schemas import TranslationProviderConfigInput
from sqlalchemy import text


def test_ensure_translation_providers_seeded_creates_one_row_per_kind(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)

    providers = list_translation_providers(in_memory_session)

    assert {provider.kind for provider in providers} == set(TRANSLATION_PROVIDER_KINDS)
    assert not any(provider.enabled for provider in providers)


def test_ensure_translation_providers_seeded_is_idempotent(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)
    ensure_translation_providers_seeded(in_memory_session)

    providers = list_translation_providers(in_memory_session)

    assert len(providers) == len(TRANSLATION_PROVIDER_KINDS)


def test_ensure_translation_providers_seeded_keeps_existing_credentials(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)
    provider = next(p for p in list_translation_providers(in_memory_session) if p.kind == "deepl")
    assert provider.id is not None
    update_translation_provider(
        in_memory_session, provider.id, TranslationProviderConfigInput(api_key="my-key")
    )

    ensure_translation_providers_seeded(in_memory_session)

    refreshed = get_translation_provider(in_memory_session, provider.id)
    assert refreshed is not None
    assert refreshed.api_key == "my-key"


def test_get_translation_provider_returns_none_when_missing(in_memory_session):
    assert get_translation_provider(in_memory_session, 1) is None


def test_mark_connection_verified_sets_the_flag(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)
    provider = list_translation_providers(in_memory_session)[0]
    assert provider.id is not None

    mark_connection_verified(in_memory_session, provider)

    refreshed = get_translation_provider(in_memory_session, provider.id)
    assert refreshed is not None
    assert refreshed.connection_verified is True


def test_update_translation_provider_replaces_fields(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)
    provider = list_translation_providers(in_memory_session)[0]
    assert provider.id is not None

    updated = update_translation_provider(
        in_memory_session,
        provider.id,
        TranslationProviderConfigInput(enabled=False, api_key="secret-key"),
    )

    assert updated is not None
    assert updated.enabled is False
    assert updated.api_key == "secret-key"


def test_update_translation_provider_returns_none_when_missing(in_memory_session):
    result = update_translation_provider(in_memory_session, 1, TranslationProviderConfigInput())
    assert result is None


def test_secrets_are_encrypted_at_rest(in_memory_session):
    ensure_translation_providers_seeded(in_memory_session)
    provider = list_translation_providers(in_memory_session)[0]
    assert provider.id is not None

    update_translation_provider(
        in_memory_session, provider.id, TranslationProviderConfigInput(api_key="secret-key")
    )

    row = in_memory_session.execute(
        text("SELECT api_key FROM translationproviderconfig WHERE id = :id"),
        {"id": provider.id},
    ).one()

    assert row.api_key.startswith(ENCRYPTED_PREFIX)
    assert "secret-key" not in row.api_key
