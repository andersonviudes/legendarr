import logging

from legendarr_backend.logging.setup import configure_logging
from legendarr_backend.system.read_logs import list_recent_logs


def test_list_recent_logs_returns_recent_lines(isolated_log_buffer):
    configure_logging()
    logger = logging.getLogger("legendarr_backend.system.test_read_logs")

    logger.error("read_logs test boom")

    lines = list_recent_logs()
    assert any("read_logs test boom" in line.text and line.level == "ERROR" for line in lines)


def test_list_recent_logs_filters_by_min_level(isolated_log_buffer):
    configure_logging()
    logger = logging.getLogger("legendarr_backend.system.test_read_logs")

    logger.info("read_logs info line")

    lines = list_recent_logs(min_level=logging.ERROR)
    assert not any("read_logs info line" in line.text for line in lines)


def test_list_recent_logs_respects_limit(isolated_log_buffer):
    configure_logging()
    logger = logging.getLogger("legendarr_backend.system.test_read_logs")
    for i in range(5):
        logger.error("read_logs limit line %s", i)

    lines = list_recent_logs(limit=2)
    assert len(lines) == 2
