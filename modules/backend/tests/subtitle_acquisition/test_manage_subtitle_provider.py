from legendarr_backend.security.secrets import ENCRYPTED_PREFIX
from legendarr_backend.subtitle_acquisition.manage_subtitle_provider import (
    ensure_subtitle_providers_seeded,
    get_subtitle_provider,
    list_subtitle_providers,
    mark_connection_verified,
    update_subtitle_provider,
)
from legendarr_backend.subtitle_acquisition.models import SUBTITLE_PROVIDER_KINDS
from legendarr_backend.subtitle_acquisition.schemas import SubtitleProviderConfigInput
from sqlalchemy import text


def test_ensure_subtitle_providers_seeded_creates_one_row_per_kind(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)

    providers = list_subtitle_providers(in_memory_session)

    assert {provider.kind for provider in providers} == set(SUBTITLE_PROVIDER_KINDS)
    assert not any(provider.enabled for provider in providers)


def test_ensure_subtitle_providers_seeded_is_idempotent(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)
    ensure_subtitle_providers_seeded(in_memory_session)

    providers = list_subtitle_providers(in_memory_session)

    assert len(providers) == len(SUBTITLE_PROVIDER_KINDS)


def test_ensure_subtitle_providers_seeded_keeps_existing_credentials(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)
    provider = next(
        p for p in list_subtitle_providers(in_memory_session) if p.kind == "opensubtitles"
    )
    update_subtitle_provider(
        in_memory_session, provider.id, SubtitleProviderConfigInput(api_key="my-key")
    )

    ensure_subtitle_providers_seeded(in_memory_session)

    refreshed = get_subtitle_provider(in_memory_session, provider.id)
    assert refreshed.api_key == "my-key"


def test_get_subtitle_provider_returns_none_when_missing(in_memory_session):
    assert get_subtitle_provider(in_memory_session, 1) is None


def test_mark_connection_verified_sets_the_flag(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)
    provider = next(
        p for p in list_subtitle_providers(in_memory_session) if p.kind == "napiprojekt"
    )

    mark_connection_verified(in_memory_session, provider)

    refreshed = get_subtitle_provider(in_memory_session, provider.id)
    assert refreshed.connection_verified is True


def test_update_subtitle_provider_replaces_fields(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)
    provider = list_subtitle_providers(in_memory_session)[0]

    updated = update_subtitle_provider(
        in_memory_session,
        provider.id,
        SubtitleProviderConfigInput(enabled=False, api_key="secret-key"),
    )

    assert updated.enabled is False
    assert updated.api_key == "secret-key"


def test_update_subtitle_provider_returns_none_when_missing(in_memory_session):
    assert update_subtitle_provider(in_memory_session, 1, SubtitleProviderConfigInput()) is None


def test_secrets_are_encrypted_at_rest(in_memory_session):
    ensure_subtitle_providers_seeded(in_memory_session)
    provider = list_subtitle_providers(in_memory_session)[0]

    update_subtitle_provider(
        in_memory_session,
        provider.id,
        SubtitleProviderConfigInput(api_key="secret-key", password="secret-pass"),
    )

    row = in_memory_session.execute(
        text("SELECT api_key, password FROM subtitleproviderconfig WHERE id = :id"),
        {"id": provider.id},
    ).one()

    assert row.api_key.startswith(ENCRYPTED_PREFIX)
    assert row.password.startswith(ENCRYPTED_PREFIX)
    assert "secret-key" not in row.api_key
    assert "secret-pass" not in row.password
