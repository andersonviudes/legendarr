from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_ROOT = Path(__file__).resolve().parent.parent


def get_templates(feature_dir: str) -> Jinja2Templates:
    """Build a Jinja2Templates instance scoped to a single feature's templates.

    Keeps each VSA slice self-contained instead of sharing one global
    templates/ directory.
    """
    return Jinja2Templates(directory=str(TEMPLATES_ROOT / feature_dir / "templates"))
