import logging
import sys

from legendarr_backend.logging.setup import RingBufferHandler, configure_logging, get_log_records


def test_configure_logging_sets_level_and_stdout_stream(monkeypatch):
    calls = {}

    def fake_basic_config(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    configure_logging(level=logging.DEBUG)

    assert calls["level"] == logging.DEBUG
    assert calls["stream"] is sys.stdout


def test_configure_logging_attaches_ring_buffer_handler_once():
    configure_logging()
    configure_logging()

    ring_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RingBufferHandler)
    ]
    assert len(ring_handlers) == 1


def test_ring_buffer_handler_records_recent_log_lines():
    configure_logging()
    logger = logging.getLogger("legendarr_backend.logging.test_setup")

    logger.error("boom")

    last_record = get_log_records()[-1]
    assert last_record.levelno == logging.ERROR
    assert "boom" in last_record.text
