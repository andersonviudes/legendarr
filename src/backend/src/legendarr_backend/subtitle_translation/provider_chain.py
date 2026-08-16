from collections.abc import Callable

from sqlmodel import Session, col, select

from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.plugins import plugin_provider_classes
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)
from legendarr_backend.subtitle_translation.providers.llm import LLMTranslationProvider

_ProviderFactory = Callable[[TranslationProviderConfig], TranslationProvider]

_PROVIDER_CLASSES: dict[str, _ProviderFactory] = {
    "deepl": DeepLTranslationProvider,
    "google": GoogleTranslationProvider,
    "libretranslate": LibreTranslateTranslationProvider,
    "llm": LLMTranslationProvider,
}


def _all_provider_classes() -> dict[str, _ProviderFactory]:
    # Dynamically-loaded plugins (ROADMAP.md 0.9.0) merged in on top of the built-ins —
    # a plugin `kind` can never collide with a built-in one, `plugins.load_plugin_providers`
    # already rejects that case at load time.
    return {**_PROVIDER_CLASSES, **plugin_provider_classes()}


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
    provider_classes = _all_provider_classes()
    return [provider_classes[config.kind](config) for config in ready]
