from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from legendarr_web.i18n.translator import current_locale, translate

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = TEMPLATES_ROOT / "static" / "icons"


def _icon(name: str) -> Markup:
    """Inline a vendored Lucide SVG (static/icons/<name>.svg) into a template."""
    return Markup((ICONS_DIR / f"{name}.svg").read_text())


def _t(key: str, **kwargs: object) -> str:
    """Translate `key` into the current request's locale (`i18n.translator.current_locale`,
    set by `i18n.resolve_locale.resolve_locale`). A plain global rather than a
    `pass_context` one — `current_locale` is a `ContextVar`, not `request.state`, so this
    works the same called directly in a template or from a macro imported via
    `{% from "macros.html" import x %}` (no `with context`, which a `pass_context`
    function tied to `request` couldn't reach — see `translator.py`)."""
    return translate(current_locale.get(), key, **kwargs)


def get_templates(feature_dir: str) -> Jinja2Templates:
    """Build a Jinja2Templates instance scoped to a single feature's templates.

    Keeps each VSA slice self-contained instead of sharing one global
    templates/ directory, while still resolving `{% extends "base.html" %}`
    against the shared layout in this top-level `templates/` package.
    """
    templates = Jinja2Templates(
        directory=[
            str(TEMPLATES_ROOT / feature_dir / "templates"),
            str(Path(__file__).resolve().parent),
        ]
    )
    templates.env.globals["icon"] = _icon
    templates.env.globals["t"] = _t
    return templates
