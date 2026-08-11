from collections.abc import Callable

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)

_PROVIDER_CLASSES: dict[str, Callable[[TranslationProviderConfig], TranslationProvider]] = {
    "deepl": DeepLTranslationProvider,
    "google": GoogleTranslationProvider,
    "libretranslate": LibreTranslateTranslationProvider,
}


def resolve_provider_chain(
    session: Session, default_kind: str | None = None
) -> list[TranslationProvider]:
    """Ordered, ready-to-call translation providers: enabled + credentialed
    `TranslationProviderConfig` rows, `id` ascending (the catalog's insertion order —
    `deepl`, `google`, `libretranslate`). The first is the primary provider, the rest are
    tried in order if an earlier one raises. An empty list means nothing usable is
    configured — callers log and skip, this is never treated as an error.

    `default_kind` (the Settings-configured `default_translation_provider`, when set) is
    moved to the front if it's among the resolved providers — everything else keeps its
    `id`-ascending order. A default that isn't enabled/credentialed, or isn't set, leaves
    the chain exactly as it was before this parameter existed.
    """
    configs = session.exec(
        select(TranslationProviderConfig)
        .where(TranslationProviderConfig.enabled)
        .order_by(col(TranslationProviderConfig.id))
    ).all()
    ready = [config for config in configs if config.has_credentials]
    ready.sort(key=lambda config: config.kind != default_kind)
    return [_PROVIDER_CLASSES[config.kind](config) for config in ready]
