"""Dynamic plugin loading for `TranslationProvider` implementations (ROADMAP.md 0.9.0).

A plugin is a `PluginTranslationProvider`-shaped class (see `providers/base.py`),
reachable on the container's `sys.path`, that the operator opts into by listing it in
`Settings.translation_plugin_packages` (`module.path:ClassName` entries). Loading never
raises: any bad entry — an unimportable path, a missing attribute, a `kind` collision, a
`plugin_api_version` mismatch — is skipped and logged, so one broken plugin never takes
the built-in providers down with it, mirroring `provider_chain.resolve_provider_chain`'s
"an empty/reduced chain is never an error" posture.
"""

import importlib
import logging
from functools import lru_cache

from legendarr_backend.config.settings import get_settings
from legendarr_backend.subtitle_translation.models import TRANSLATION_PROVIDER_KINDS
from legendarr_backend.subtitle_translation.providers.base import PluginTranslationProvider

logger = logging.getLogger(__name__)

# Bumped on any breaking change to the `PluginTranslationProvider` contract. A plugin
# declaring a different version is skipped rather than loaded and risking a runtime
# `AttributeError`/`TypeError` mismatch further down the line.
SUPPORTED_PLUGIN_API_VERSION = 1

_REQUIRED_ATTRS = (
    "kind",
    "label",
    "credential_fields",
    "required_credential_fields",
    "plugin_api_version",
)


def _load_one(entry: str) -> type[PluginTranslationProvider] | None:
    module_path, _, class_name = entry.partition(":")
    if not module_path or not class_name:
        logger.warning(
            "translation plugin entry %r is malformed, expected 'module.path:ClassName'", entry
        )
        return None
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        logger.warning("translation plugin %r could not be imported", entry, exc_info=True)
        return None
    plugin_class = getattr(module, class_name, None)
    if plugin_class is None:
        logger.warning("translation plugin %r has no attribute %r", module_path, class_name)
        return None
    missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(plugin_class, attr)]
    if missing:
        logger.warning(
            "translation plugin %r is missing required attribute(s): %s",
            entry,
            ", ".join(missing),
        )
        return None
    if plugin_class.plugin_api_version != SUPPORTED_PLUGIN_API_VERSION:
        logger.warning(
            "translation plugin %r declares plugin_api_version=%r, legendarr supports %r — skipped",
            entry,
            plugin_class.plugin_api_version,
            SUPPORTED_PLUGIN_API_VERSION,
        )
        return None
    return plugin_class


@lru_cache
def load_plugin_providers() -> dict[str, type[PluginTranslationProvider]]:
    """Every successfully-loaded plugin class, keyed by its declared `kind`. Cached for
    the process lifetime — `Settings.translation_plugin_packages` is env-var-only
    (ROADMAP.md 0.9.0), so this can't change without a restart anyway.
    """
    registry: dict[str, type[PluginTranslationProvider]] = {}
    for entry in get_settings().translation_plugin_package_list:
        plugin_class = _load_one(entry)
        if plugin_class is None:
            continue
        kind = plugin_class.kind
        if kind in TRANSLATION_PROVIDER_KINDS:
            logger.warning(
                "translation plugin %r's kind %r collides with a built-in provider — skipped",
                entry,
                kind,
            )
            continue
        if kind in registry:
            logger.warning(
                "translation plugin %r's kind %r collides with another plugin — skipped",
                entry,
                kind,
            )
            continue
        registry[kind] = plugin_class
    return registry


def plugin_kinds() -> tuple[str, ...]:
    return tuple(load_plugin_providers())


def plugin_provider_classes() -> dict[str, type[PluginTranslationProvider]]:
    return dict(load_plugin_providers())


def plugin_label(kind: str) -> str | None:
    plugin_class = load_plugin_providers().get(kind)
    return plugin_class.label if plugin_class is not None else None


def plugin_credential_fields(kind: str) -> tuple[str, ...]:
    plugin_class = load_plugin_providers().get(kind)
    return plugin_class.credential_fields if plugin_class is not None else ()


def plugin_required_credential_fields(kind: str) -> tuple[str, ...]:
    plugin_class = load_plugin_providers().get(kind)
    return plugin_class.required_credential_fields if plugin_class is not None else ()
