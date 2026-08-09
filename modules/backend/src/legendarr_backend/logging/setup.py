import logging
import sys
from collections import deque
from dataclasses import dataclass

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_BUFFER_SIZE = 1000


@dataclass(frozen=True)
class LogRecordEntry:
    text: str
    levelno: int


class RingBufferHandler(logging.Handler):
    """Keeps the last `_BUFFER_SIZE` formatted log records in memory.

    Backs the System page's log viewer (ROADMAP 0.5.0) so day-to-day operation
    doesn't require shelling into the container. History resets on restart/crash —
    this is for recent activity, not post-mortem forensics.
    """

    def __init__(self) -> None:
        super().__init__()
        self._records: deque[LogRecordEntry] = deque(maxlen=_BUFFER_SIZE)

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(LogRecordEntry(text=self.format(record), levelno=record.levelno))

    def records(self) -> list[LogRecordEntry]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


_ring_buffer_handler = RingBufferHandler()


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format=_FORMAT,
        stream=sys.stdout,
    )
    root = logging.getLogger()
    if _ring_buffer_handler not in root.handlers:
        _ring_buffer_handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(_ring_buffer_handler)


def get_log_records() -> list[LogRecordEntry]:
    """Return the in-memory log history, oldest first."""
    return _ring_buffer_handler.records()


def reset_log_records() -> None:
    """Clear the in-memory log history. For test isolation only."""
    _ring_buffer_handler.clear()
