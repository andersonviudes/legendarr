from legendarr_backend.subtitle_acquisition.manage_subtitle_provider import (
    get_subtitle_provider,
)
from legendarr_backend.subtitle_acquisition.manage_subtitle_proxy import (
    create_subtitle_proxy,
    delete_subtitle_proxy,
    get_subtitle_proxy,
    list_subtitle_proxies,
    set_subtitle_proxy_enabled,
    update_subtitle_proxy,
)
from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.schemas import SubtitleProxyInput


def _flaresolverr_input(**overrides) -> SubtitleProxyInput:
    data = {"name": "FlareSolverr", "host": "http://10.0.1.1:8191/"}
    data.update(overrides)
    return SubtitleProxyInput(**data)


def test_create_and_list_subtitle_proxy(in_memory_session):
    create_subtitle_proxy(in_memory_session, _flaresolverr_input())

    proxies = list_subtitle_proxies(in_memory_session)

    assert [proxy.name for proxy in proxies] == ["FlareSolverr"]


def test_get_subtitle_proxy_returns_none_when_missing(in_memory_session):
    assert get_subtitle_proxy(in_memory_session, 1) is None


def test_update_subtitle_proxy_replaces_fields(in_memory_session):
    proxy = create_subtitle_proxy(in_memory_session, _flaresolverr_input())

    updated = update_subtitle_proxy(
        in_memory_session, proxy.id, _flaresolverr_input(host="http://10.0.1.2:8191/")
    )

    assert updated.host == "http://10.0.1.2:8191/"


def test_update_subtitle_proxy_returns_none_when_missing(in_memory_session):
    assert update_subtitle_proxy(in_memory_session, 1, _flaresolverr_input()) is None


def test_set_subtitle_proxy_enabled_flips_flag(in_memory_session):
    proxy = create_subtitle_proxy(in_memory_session, _flaresolverr_input(enabled=True))

    disabled = set_subtitle_proxy_enabled(in_memory_session, proxy.id, False)
    assert disabled.enabled is False

    enabled = set_subtitle_proxy_enabled(in_memory_session, proxy.id, True)
    assert enabled.enabled is True


def test_set_subtitle_proxy_enabled_returns_none_when_missing(in_memory_session):
    assert set_subtitle_proxy_enabled(in_memory_session, 1, False) is None


def test_delete_subtitle_proxy(in_memory_session):
    proxy = create_subtitle_proxy(in_memory_session, _flaresolverr_input())

    assert delete_subtitle_proxy(in_memory_session, proxy.id) is True
    assert list_subtitle_proxies(in_memory_session) == []


def test_delete_subtitle_proxy_returns_false_when_missing(in_memory_session):
    assert delete_subtitle_proxy(in_memory_session, 1) is False


def test_delete_subtitle_proxy_unassigns_it_from_providers(in_memory_session):
    proxy = create_subtitle_proxy(in_memory_session, _flaresolverr_input())
    provider = SubtitleProviderConfig(kind="addic7ed", proxy_id=proxy.id)
    in_memory_session.add(provider)
    in_memory_session.commit()
    provider_id = provider.id

    assert delete_subtitle_proxy(in_memory_session, proxy.id) is True

    in_memory_session.expunge_all()
    assert get_subtitle_provider(in_memory_session, provider_id).proxy_id is None
