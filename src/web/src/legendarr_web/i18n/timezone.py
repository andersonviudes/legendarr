from contextvars import ContextVar
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, available_timezones

# Sibling setting to `translator.py`'s locale — instance-wide timezone used to display
# timestamps across legendarr_web. Doesn't affect what's persisted (always naive-but-UTC,
# see `authentication/manage_authentication.py`'s `_utcnow()` comment on the backend) or
# when scheduled jobs run (`legendarr_backend/scheduling/scheduler.py` pins APScheduler to
# UTC too) — this only ever changes how an already-UTC value already fetched from the
# backend gets rendered.
DEFAULT_TIMEZONE = "UTC"

SUPPORTED_TIMEZONES: list[str] = sorted(available_timezones())

# Holds the active request's timezone so the `local_datetime` Jinja filter
# (`templates/loader.py`) can read it from anywhere, same `ContextVar` pattern as
# `translator.py`'s `current_locale` — set once per request by
# `i18n.resolve_locale.resolve_locale`.
current_timezone: ContextVar[str] = ContextVar("current_timezone", default=DEFAULT_TIMEZONE)

_DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def to_local(value: str) -> str:
    """Convert a backend-supplied ISO datetime string to the active request's timezone,
    keeping the same "YYYY-MM-DD HH:MM:SS" shape every template already showed via its
    own `value[:19].replace("T", " ")` — a pure display change, nothing else. A naive
    value (every persisted timestamp is naive-but-UTC) is treated as UTC before
    converting."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(ZoneInfo(current_timezone.get())).strftime(_DISPLAY_FORMAT)
