from sqlmodel import Session, select

from legendarr_backend.subtitle_acquisition.models import SubtitleProxy
from legendarr_backend.subtitle_acquisition.schemas import SubtitleProxyInput


def create_subtitle_proxy(session: Session, data: SubtitleProxyInput) -> SubtitleProxy:
    proxy = SubtitleProxy.model_validate(data.model_dump())
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    return proxy


def list_subtitle_proxies(session: Session) -> list[SubtitleProxy]:
    return list(session.exec(select(SubtitleProxy)).all())


def get_subtitle_proxy(session: Session, proxy_id: int) -> SubtitleProxy | None:
    return session.get(SubtitleProxy, proxy_id)


def update_subtitle_proxy(
    session: Session, proxy_id: int, data: SubtitleProxyInput
) -> SubtitleProxy | None:
    proxy = session.get(SubtitleProxy, proxy_id)
    if proxy is None:
        return None
    for field, value in data.model_dump().items():
        setattr(proxy, field, value)
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    return proxy


def set_subtitle_proxy_enabled(
    session: Session, proxy_id: int, enabled: bool
) -> SubtitleProxy | None:
    proxy = session.get(SubtitleProxy, proxy_id)
    if proxy is None:
        return None
    proxy.enabled = enabled
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    return proxy


def delete_subtitle_proxy(session: Session, proxy_id: int) -> bool:
    proxy = session.get(SubtitleProxy, proxy_id)
    if proxy is None:
        return False
    # The FK's ON DELETE SET NULL (enforced via PRAGMA foreign_keys=ON) unassigns this proxy
    # from any SubtitleProviderConfig referencing it, rather than blocking the delete.
    session.delete(proxy)
    session.commit()
    return True
