from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = TEMPLATES_ROOT / "static" / "icons"


def _icon(name: str) -> Markup:
    """Inline a vendored Lucide SVG (static/icons/<name>.svg) into a template."""
    return Markup((ICONS_DIR / f"{name}.svg").read_text())


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
    return templates
