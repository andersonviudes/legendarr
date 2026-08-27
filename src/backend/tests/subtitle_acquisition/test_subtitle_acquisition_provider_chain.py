from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.provider_chain import resolve_subtitle_provider_chain
from legendarr_backend.subtitle_acquisition.providers.addic7ed import Addic7edProvider
from legendarr_backend.subtitle_acquisition.providers.animekalesi import AnimeKalesiProvider
from legendarr_backend.subtitle_acquisition.providers.animetosho import AnimeToshoProvider
from legendarr_backend.subtitle_acquisition.providers.betaseries import BetaSeriesProvider
from legendarr_backend.subtitle_acquisition.providers.greeksubtitles import (
    GreekSubtitlesProvider,
)
from legendarr_backend.subtitle_acquisition.providers.legendas_net import LegendasNetProvider
from legendarr_backend.subtitle_acquisition.providers.napiprojekt import NapiprojektProvider
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import OpenSubtitlesProvider
from legendarr_backend.subtitle_acquisition.providers.subdl import SubdlProvider
from legendarr_backend.subtitle_acquisition.providers.subsource import SubsourceProvider
from legendarr_backend.subtitle_acquisition.providers.supersubtitles import (
    SupersubtitlesProvider,
)
from legendarr_backend.subtitle_acquisition.providers.tvsubtitles import TVsubtitlesProvider
from legendarr_backend.subtitle_acquisition.providers.yify_subtitles import YifySubtitlesProvider


def test_resolve_subtitle_provider_chain_returns_empty_list_when_nothing_configured(
    in_memory_session,
):
    in_memory_session.add(SubtitleProviderConfig(kind="opensubtitles", enabled=False))
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_skips_disabled_providers(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(
            kind="opensubtitles", enabled=False, username="user", password="pass"
        )
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
    # A synthetic kind deliberately outside `SUBTITLE_PROVIDER_KINDS` — every real kind
    # has a `SubtitleProvider` implementation as of 0.6.0, so there's no longer a
    # registered-but-unimplemented example to reuse here.
    in_memory_session.add(SubtitleProviderConfig(kind="not_a_real_provider", enabled=True))
    in_memory_session.commit()

    assert resolve_subtitle_provider_chain(in_memory_session) == []


def test_resolve_subtitle_provider_chain_returns_ready_providers(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(kind="opensubtitles", enabled=True, username="user", password="pass")
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


def test_resolve_subtitle_provider_chain_resolves_subdl_when_credentialed(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="subdl", enabled=True, api_key="a-key"))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], SubdlProvider)


def test_resolve_subtitle_provider_chain_resolves_tvsubtitles_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="tvsubtitles", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], TVsubtitlesProvider)


def test_resolve_subtitle_provider_chain_resolves_legendas_net_when_credentialed(
    in_memory_session,
):
    in_memory_session.add(
        SubtitleProviderConfig(kind="legendas_net", enabled=True, username="u", password="p")
    )
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], LegendasNetProvider)


def test_resolve_subtitle_provider_chain_resolves_napiprojekt_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="napiprojekt", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], NapiprojektProvider)


def test_resolve_subtitle_provider_chain_resolves_subsource_when_credentialed(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="subsource", enabled=True, api_key="a-key"))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], SubsourceProvider)


def test_resolve_subtitle_provider_chain_resolves_animetosho_when_credentialed(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="animetosho", enabled=True, api_key="a-key"))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], AnimeToshoProvider)


def test_resolve_subtitle_provider_chain_resolves_animetosho_without_api_key(in_memory_session):
    """animetosho's api_key is optional (see `models.py`'s `_API_KEY_KINDS` comment) —
    enabling it needs no credential at all, unlike subdl/subsource/betaseries."""
    in_memory_session.add(SubtitleProviderConfig(kind="animetosho", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], AnimeToshoProvider)


def test_resolve_subtitle_provider_chain_resolves_supersubtitles_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="supersubtitles", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], SupersubtitlesProvider)


def test_resolve_subtitle_provider_chain_resolves_animekalesi_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="animekalesi", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], AnimeKalesiProvider)


def test_resolve_subtitle_provider_chain_resolves_greeksubtitles_when_enabled(in_memory_session):
    in_memory_session.add(SubtitleProviderConfig(kind="greeksubtitles", enabled=True))
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], GreekSubtitlesProvider)


def test_resolve_subtitle_provider_chain_resolves_betaseries_when_credentialed(in_memory_session):
    in_memory_session.add(
        SubtitleProviderConfig(kind="betaseries", enabled=True, api_key="a-token")
    )
    in_memory_session.commit()

    chain = resolve_subtitle_provider_chain(in_memory_session)

    assert len(chain) == 1
    assert isinstance(chain[0], BetaSeriesProvider)
