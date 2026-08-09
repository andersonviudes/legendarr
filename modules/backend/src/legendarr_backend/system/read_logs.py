import logging

from legendarr_backend.logging.setup import get_log_records
from legendarr_backend.system.schemas import LogLineRead


def list_recent_logs(min_level: int | None = None, limit: int = 200) -> list[LogLineRead]:
    """Return the most recent log lines, oldest first, each tagged with its level name.

    `min_level` filters to records at or above that level (e.g. `logging.WARNING`
    hides DEBUG/INFO); `None` returns everything currently buffered.
    """
    records = get_log_records()
    if min_level is not None:
        records = [record for record in records if record.levelno >= min_level]
    return [
        LogLineRead(text=record.text, level=logging.getLevelName(record.levelno))
        for record in records[-limit:]
    ]
