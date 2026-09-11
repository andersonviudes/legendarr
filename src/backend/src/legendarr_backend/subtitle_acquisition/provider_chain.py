from collections.abc import Callable

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_acquisition.models import SubtitleProviderConfig
from legendarr_backend.subtitle_acquisition.providers.addic7ed import Addic7edProvider
from legendarr_backend.subtitle_acquisition.providers.animekalesi import AnimeKalesiProvider
from legendarr_backend.subtitle_acquisition.providers.animetosho import AnimeToshoProvider
from legendarr_backend.subtitle_acquisition.providers.base import SubtitleProvider
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

_PROVIDER_CLASSES: dict[str, Callable[[SubtitleProviderConfig], SubtitleProvider]] = {
    "opensubtitles": OpenSubtitlesProvider,
    "addic7ed": Addic7edProvider,
    "yify_subtitles": YifySubtitlesProvider,
    "subdl": SubdlProvider,
    "tvsubtitles": TVsubtitlesProvider,
    "legendas_net": LegendasNetProvider,
    "napiprojekt": NapiprojektProvider,
    "subsource": SubsourceProvider,
    "animetosho": AnimeToshoProvider,
    "supersubtitles": SupersubtitlesProvider,
    "animekalesi": AnimeKalesiProvider,
    "greeksubtitles": GreekSubtitlesProvider,
    "betaseries": BetaSeriesProvider,
}

# The one kind whose `search()` reads `moviehash` (`providers/opensubtitles.py`, gated
# on its own `SubtitleProviderConfig.use_hash`). Every other kind ignores the argument.
_MOVIEHASH_PROVIDER_KIND = "opensubtitles"


def resolve_subtitle_provider_chain(session: Session) -> list[SubtitleProvider]:
    """Ordered, ready-to-call subtitle providers: enabled + credentialed
    `SubtitleProviderConfig` rows among the kinds with a real `SubtitleProvider`
    implementation — every kind in `SUBTITLE_PROVIDER_KINDS` as of 0.6.0
    (`opensubtitles`, `addic7ed`, `yify_subtitles`, `subdl`, `tvsubtitles`,
    `legendas_net`, `napiprojekt`, `subsource`, `animetosho`, `supersubtitles`,
    `animekalesi`, `greeksubtitles`, `betaseries`), `id` ascending.
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


def moviehash_search_enabled(session: Session) -> bool:
    """Whether any usable provider would actually search by `moviehash`.

    Computing the hash means reading the video file itself
    (`opensubtitles_hash.compute_opensubtitles_hash`), which on a network mount that
    stopped answering costs a full timeout per media file and abandons a reader thread
    that never comes back. Nothing else in the search path touches the video, so when
    the only provider that reads the hash is disabled, uncredentialed or has `use_hash`
    off, that's pure cost for a value no one looks at — `search_context` asks this first
    instead of hashing unconditionally.
    """
    config = session.exec(
        select(SubtitleProviderConfig).where(
            SubtitleProviderConfig.kind == _MOVIEHASH_PROVIDER_KIND
        )
    ).first()
    return config is not None and config.enabled and config.has_credentials and config.use_hash
