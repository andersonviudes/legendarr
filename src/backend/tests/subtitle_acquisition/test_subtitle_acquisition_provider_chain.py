from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.addic7ed import Addic7edProvider
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import OpenSubtitlesProvider
from legendarr_backend.subtitle_acquisition.providers.yify_subtitles import YifySubtitlesProvider


def test_resolve_subtitle_provider_chain_returns_empty_list_when_nothing_configured(
    in_memory_session,
):
    in_memory_session.add(SubtitleProviderConfig(kind="opensubtitles", enabled=False))
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_skips_disabled_providers(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(kind="opensubtitles", enabled=False, api_key="a-key")
    )
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_skips_providers_without_credentials(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="opensubtitles", enabled=True))
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_skips_kinds_with_no_real_implementation(
    in_memory_session,
):
    in_memory_session.add(SubtitleProviderConfig(kind="subdl", enabled=True, api_key="a-key"))
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_returns_ready_providers(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(kind="opensubtitles", enabled=True, api_key="a-key")
    )
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], OpenSubtitlesProvider)


def test_resolve_subtitle_provider_chain_resolves_addic7ed_when_credentialed(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(kind="addic7ed", enabled=True, username="u", password="p")
    )
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], Addic7edProvider)


def test_resolve_subtitle_provider_chain_resolves_yify_subtitles_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="yify_subtitles", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], YifySubtitlesProvider)
