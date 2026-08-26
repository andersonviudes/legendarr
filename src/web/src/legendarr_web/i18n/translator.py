import json
from contextvars import ContextVar
from pathlib import Path

# ROADMAP.md 0.19.0 — i18n scaffolding. Unrelated to `languages.py`'s
# `SUPPORTED_LANGUAGES` (subtitle content languages) — this is the display language of
# legendarr_web itself, single shared admin account so it's one instance-wide preference.
# Each name is spelled in its own language (not translated into the active locale), so a
# user can always find their language regardless of what's currently selected.
SUPPORTED_UI_LOCALES: list[tuple[str, str]] = [
    ("en", "English"),
    ("es", "Español"),
    ("pt-BR", "Português (Brasil)"),
]

DEFAULT_LOCALE = "en"

# Holds the active request's locale so the `t()` Jinja global (`templates/loader.py`) can
# read it from anywhere — including a macro imported via `{% from "macros.html" import
# x %}` without `with context`, which a `pass_context` global can't reach since Jinja
# doesn't thread the caller's `request` var into an imported macro's own context. A
# `ContextVar` sidesteps that: it's set once per request by
# `i18n.resolve_locale.resolve_locale` and correctly isolated per concurrent request by
# asyncio (and propagated into a threadpool render, if Starlette ever uses one, since
# anyio copies the context across that boundary).
current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)

_LOCALES_DIR = Path(__file__).parent / "locales"


def _load_catalog(locale: str) -> dict[str, str]:
    return json.loads((_LOCALES_DIR / f"{locale}.json").read_text())


# Loaded once at import time — flat, dot-namespaced key -> string maps (e.g.
# "nav.dashboard", "common.save"), one JSON file per supported locale.
_CATALOGS: dict[str, dict[str, str]] = {
    code: _load_catalog(code) for code, _ in SUPPORTED_UI_LOCALES
}


def translate(locale: str, key: str, **kwargs: object) -> str:
    """Look up `key` in `locale`'s catalog, falling back to `en` and then the raw key
    itself so a missing translation degrades to something visible instead of crashing
    the page."""
    catalog = _CATALOGS.get(locale, _CATALOGS[DEFAULT_LOCALE])
    text = catalog.get(key) or _CATALOGS[DEFAULT_LOCALE].get(key) or key
    return text.format(**kwargs) if kwargs else text
