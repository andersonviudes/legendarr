from sqlmodel import Session, select

from legendarr_backend.subtitle_translation.models import TranslationProviderConfig
from legendarr_backend.subtitle_translation.providers.base import TranslationProvider
from legendarr_backend.subtitle_translation.providers.deepl import DeepLTranslationProvider
from legendarr_backend.subtitle_translation.providers.google import GoogleTranslationProvider
from legendarr_backend.subtitle_translation.providers.libretranslate import (
    LibreTranslateTranslationProvider,
)

_PROVIDER_CLASSES: dict[str, type[TranslationProvider]] = {
    "deepl": DeepLTranslationProvider,
    "google": GoogleTranslationProvider,
    "libretranslate": LibreTranslateTranslationProvider,
}


def resolve_provider_chain(session: Session) -> list[TranslationProvider]:
    """Ordered, ready-to-call translation providers: enabled + credentialed
    `TranslationProviderConfig` rows, `id` ascending (the catalog's insertion order —
    `deepl`, `google`, `libretranslate`). The first is the primary provider, the rest are
    tried in order if an earlier one raises. An empty list means nothing usable is
    configured — callers log and skip, this is never treated as an error.
    """
    configs = session.exec(
        select(TranslationProviderConfig)
        .where(TranslationProviderConfig.enabled)
        .order_by(TranslationProviderConfig.id)
    ).all()
    return [_PROVIDER_CLASSES[config.kind](config) for config in configs if config.has_credentials]
