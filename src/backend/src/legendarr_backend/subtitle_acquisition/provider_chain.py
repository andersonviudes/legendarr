from collections.abc import Callable

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.addic7ed import Addic7edProvider
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleProvider
from legendarr_backend.subtitle_acquisition.providers.opensubtitles import OpenSubtitlesProvider
from legendarr_backend.subtitle_acquisition.providers.yify_subtitles import YifySubtitlesProvider

_PROVIDER_CLASSES: dict[str, Callable[[SubtitleProviderConfig], SubtitleProvider]] = {
    "opensubtitles": OpenSubtitlesProvider,
    "addic7ed": Addic7edProvider,
    "yify_subtitles": YifySubtitlesProvider,
}


def resolve_subtitle_provider_chain(session: Session) -> list[SubtitleProvider]:
    """Ordered, ready-to-call subtitle providers: enabled + credentialed
    `SubtitleProviderConfig` rows among the kinds with a real `SubtitleProvider`
    implementation (today: `opensubtitles`, `addic7ed`, `yify_subtitles`), `id` ascending.
    An empty list means nothing usable is configured — callers log and skip, this is never treated
    as an error. Same shape as `subtitle_translation.provider_chain.resolve_provider_chain`,
    ready for the next `SubtitleProvider` implementation to extend `_PROVIDER_CLASSES`
    without changing this function.
    """
    configs = session.exec(
        select(SubtitleProviderConfig)
        .where(
            SubtitleProviderConfig.enabled,
            col(SubtitleProviderConfig.kind).in_(_PROVIDER_CLASSES),
        )
        .order_by(col(SubtitleProviderConfig.id))
    ).all()
    ready = [config for config in configs if config.has_credentials]
    return [_PROVIDER_CLASSES[config.kind](config) for config in ready]
