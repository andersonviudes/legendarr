from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.provider_chain import resolve_provider_chain
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.llm import LLMTranslationProvider


def test_resolve_provider_chain_orders_enabled_credentialed_providers_by_id(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
    in_memory_session.add(TranslationProviderConfig(kind="google", enabled=True, api_key="a-key"))
    in_memory_session.add(TranslationProviderConfig(kind="libretranslate", enabled=True))
    in_memory_session.commit()

    chain = resolve_provider_chain(in_memory_session)

    assert [type(provider) for provider in chain] == [
        DeepLTranslationProvider,
        GoogleTranslationProvider,
    ]


def test_resolve_provider_chain_skips_disabled_providers(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=False, api_key="a-key"))
    in_memory_session.commit()

    assert resolve_provider_chain(in_memory_session) == []


def test_resolve_provider_chain_skips_providers_missing_credentials(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key=None))
    in_memory_session.commit()

    assert resolve_provider_chain(in_memory_session) == []


def test_resolve_provider_chain_is_empty_when_nothing_configured(in_memory_session):
    assert resolve_provider_chain(in_memory_session) == []


def test_resolve_provider_chain_moves_default_to_front(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
    in_memory_session.add(TranslationProviderConfig(kind="google", enabled=True, api_key="a-key"))
    in_memory_session.add(
        TranslationProviderConfig(kind="libretranslate", enabled=True, endpoint="http://lt")
    )
    in_memory_session.commit()

    chain = resolve_provider_chain(in_memory_session, default_kind="libretranslate")

    assert [type(provider) for provider in chain] == [
        LibreTranslateTranslationProvider,
        DeepLTranslationProvider,
        GoogleTranslationProvider,
    ]


def test_resolve_provider_chain_ignores_default_not_in_resolved_list(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="deepl", enabled=True, api_key="a-key"))
    in_memory_session.add(TranslationProviderConfig(kind="google", enabled=False, api_key="a-key"))
    in_memory_session.commit()

    chain = resolve_provider_chain(in_memory_session, default_kind="google")

    assert [type(provider) for provider in chain] == [DeepLTranslationProvider]


def test_resolve_provider_chain_includes_llm_when_configured(in_memory_session):
    in_memory_session.add(TranslationProviderConfig(kind="llm", enabled=True, api_key="a-key"))
    in_memory_session.commit()

    chain = resolve_provider_chain(in_memory_session)

    assert [type(provider) for provider in chain] == [LLMTranslationProvider]
